"""SnapStream HTTP routes."""

import asyncio
import logging
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import case, delete, desc, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .config import Settings
from .db import get_db
from .dependencies import (
    bearer_scheme,
    get_app_settings,
    get_current_user,
    get_redis,
    get_s3,
    get_s3_presigner,
)
from .models import Follow, Like, Post, User
from .schemas import (
    FeedResponse,
    FollowResponse,
    HealthResponse,
    LikeResponse,
    LoginRequest,
    MediaDownloadResponse,
    MediaReference,
    MediaResponse,
    PostCreateRequest,
    PostResponse,
    PublicUserResponse,
    RegisterRequest,
    SessionResponse,
    UploadPresignRequest,
    UploadPresignResponse,
    UserResponse,
)
from .security import hash_password, new_session_token, session_digest, verify_password
from .uploads import (
    InvalidMedia,
    MediaServiceUnavailable,
    create_presigned_download,
    create_presigned_upload,
    verify_uploaded_media,
)

logger = logging.getLogger(__name__)
router = APIRouter()
Database = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Any, Depends(get_redis)]
S3Client = Annotated[Any, Depends(get_s3)]
S3Presigner = Annotated[Any, Depends(get_s3_presigner)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
CurrentUser = Annotated[User, Depends(get_current_user)]
BearerCredentials = Annotated[Any, Depends(bearer_scheme)]


def _session_response(user: User, token: str, settings: Settings) -> SessionResponse:
    return SessionResponse(
        access_token=token,
        expires_in=settings.session_ttl_seconds,
        user=UserResponse.model_validate(user),
    )


async def _save_session(redis: Any, user_id: str, settings: Settings) -> str:
    token = new_session_token()
    try:
        await redis.set(
            f"session:{session_digest(token)}",
            user_id,
            ex=settings.session_ttl_seconds,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="session service unavailable",
        ) from exc
    return token


@router.post("/auth/register", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: Database,
    redis: RedisClient,
    settings: AppSettings,
) -> SessionResponse:
    exists = await db.scalar(
        select(User.id).where(
            or_(func.lower(User.email) == payload.email, User.username == payload.username)
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail="email or username already registered")
    user = User(
        email=payload.email,
        username=payload.username,
        display_name=payload.display_name,
        password_hash=await asyncio.to_thread(hash_password, payload.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="email or username already registered",
        ) from exc
    await db.refresh(user)
    token = await _save_session(redis, user.id, settings)
    return _session_response(user, token, settings)


@router.post("/auth/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    db: Database,
    redis: RedisClient,
    settings: AppSettings,
) -> SessionResponse:
    normalized = payload.login.strip().lower()
    user = await db.scalar(
        select(User).where(
            or_(func.lower(User.email) == normalized, User.username == normalized)
        )
    )
    if user is None or not await asyncio.to_thread(
        verify_password, payload.password, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = await _save_session(redis, user.id, settings)
    return _session_response(user, token, settings)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: BearerCredentials,
    _: CurrentUser,
    redis: RedisClient,
) -> Response:
    try:
        await redis.delete(f"session:{session_digest(credentials.credentials)}")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="session service unavailable") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/me", response_model=UserResponse)
async def me(user: CurrentUser) -> User:
    return user


@router.get("/users", response_model=list[PublicUserResponse])
async def list_users(
    db: Database,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[User]:
    return list((await db.scalars(select(User).order_by(User.username).limit(limit))).all())


@router.post(
    "/uploads/presign",
    response_model=UploadPresignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def presign_upload(
    payload: UploadPresignRequest,
    user: CurrentUser,
    s3: S3Presigner,
    settings: AppSettings,
) -> UploadPresignResponse:
    try:
        return create_presigned_upload(s3, user.id, payload, settings)
    except InvalidMedia as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MediaServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _invalidate_feed(redis: Any) -> None:
    try:
        await redis.incr("feed:generation")
    except Exception:
        logger.warning("Could not invalidate feed cache", exc_info=True)


def _post_response(post: Post) -> PostResponse:
    media = None
    if post.media_key is not None:
        media = MediaResponse(
            bucket=post.media_bucket or "",
            key=post.media_key,
            content_type=post.media_content_type or "application/octet-stream",
            size_bytes=post.media_size_bytes or 0,
        )
    return PostResponse(
        id=post.id,
        body=post.body,
        likes_count=post.likes_count,
        created_at=post.created_at,
        author=PublicUserResponse.model_validate(post.author),
        media=media,
    )


@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreateRequest,
    user: CurrentUser,
    db: Database,
    redis: RedisClient,
    s3: S3Client,
    settings: AppSettings,
) -> PostResponse:
    if payload.media is not None:
        try:
            await verify_uploaded_media(s3, user.id, payload.media, settings)
        except InvalidMedia as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except MediaServiceUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    media: MediaReference | None = payload.media
    post = Post(
        author_id=user.id,
        body=payload.body,
        media_bucket=settings.s3_bucket if media else None,
        media_key=media.key if media else None,
        media_content_type=media.content_type if media else None,
        media_size_bytes=media.size_bytes if media else None,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    post.author = user
    await _invalidate_feed(redis)
    return _post_response(post)


@router.get("/posts/{post_id}/media-url", response_model=MediaDownloadResponse)
async def get_post_media_url(
    post_id: str,
    db: Database,
    s3: S3Presigner,
    settings: AppSettings,
) -> MediaDownloadResponse:
    post = await db.get(Post, post_id)
    if post is None or post.media_key is None or post.media_bucket is None:
        raise HTTPException(status_code=404, detail="post media not found")
    try:
        return create_presigned_download(s3, post.media_bucket, post.media_key, settings)
    except MediaServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/posts/{post_id}/likes", response_model=LikeResponse)
async def like_post(
    post_id: str,
    user: CurrentUser,
    db: Database,
    redis: RedisClient,
) -> LikeResponse:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    existing = await db.get(Like, (user.id, post_id))
    if existing is None:
        db.add(Like(user_id=user.id, post_id=post_id))
        await db.execute(
            update(Post).where(Post.id == post_id).values(likes_count=Post.likes_count + 1)
        )
        try:
            await db.commit()
            await _invalidate_feed(redis)
        except IntegrityError:
            await db.rollback()
    await db.refresh(post)
    return LikeResponse(post_id=post_id, likes_count=post.likes_count, liked=True)


@router.delete("/posts/{post_id}/likes", response_model=LikeResponse)
async def unlike_post(
    post_id: str,
    user: CurrentUser,
    db: Database,
    redis: RedisClient,
) -> LikeResponse:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    removed = await db.execute(
        delete(Like).where(Like.user_id == user.id, Like.post_id == post_id)
    )
    if removed.rowcount:
        await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(likes_count=case((Post.likes_count > 0, Post.likes_count - 1), else_=0))
        )
        await db.commit()
        await _invalidate_feed(redis)
    await db.refresh(post)
    return LikeResponse(post_id=post_id, likes_count=post.likes_count, liked=False)


async def _set_follow(
    *, following: bool, target_id: str, user: User, db: AsyncSession
) -> FollowResponse:
    if target_id == user.id:
        raise HTTPException(status_code=422, detail="users cannot follow themselves")
    if await db.get(User, target_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    existing = await db.get(Follow, (user.id, target_id))
    if following and existing is None:
        db.add(Follow(follower_id=user.id, followed_id=target_id))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
    elif not following and existing is not None:
        await db.delete(existing)
        await db.commit()
    return FollowResponse(user_id=target_id, following=following)


@router.post("/users/{user_id}/follow", response_model=FollowResponse)
async def follow_user(user_id: str, user: CurrentUser, db: Database) -> FollowResponse:
    return await _set_follow(following=True, target_id=user_id, user=user, db=db)


@router.delete("/users/{user_id}/follow", response_model=FollowResponse)
async def unfollow_user(user_id: str, user: CurrentUser, db: Database) -> FollowResponse:
    return await _set_follow(following=False, target_id=user_id, user=user, db=db)


async def _read_feed_cache(redis: Any, key: str) -> FeedResponse | None:
    try:
        cached = await redis.get(key)
        return FeedResponse.model_validate_json(cached) if cached else None
    except Exception:
        logger.warning("Could not read feed cache", exc_info=True)
        return None


async def _write_feed_cache(redis: Any, key: str, feed: FeedResponse, ttl: int) -> None:
    try:
        await redis.set(key, feed.model_dump_json(), ex=ttl)
    except Exception:
        logger.warning("Could not write feed cache", exc_info=True)


@router.get("/feed", response_model=FeedResponse)
async def feed(
    db: Database,
    redis: RedisClient,
    settings: AppSettings,
    kind: Literal["recent", "trending"] = Query(default="recent"),
    limit: int = Query(default=20, ge=1, le=100),
) -> FeedResponse:
    try:
        generation = await redis.get("feed:generation") or "0"
        if isinstance(generation, bytes):
            generation = generation.decode()
    except Exception:
        generation = "uncached"
    cache_key = f"feed:{generation}:{kind}:{limit}"
    cached = await _read_feed_cache(redis, cache_key)
    if cached is not None:
        return cached

    ordering = (
        (desc(Post.created_at), desc(Post.id))
        if kind == "recent"
        else (desc(Post.likes_count), desc(Post.created_at), desc(Post.id))
    )
    posts = list(
        (
            await db.scalars(
                select(Post).options(selectinload(Post.author)).order_by(*ordering).limit(limit)
            )
        ).all()
    )
    response = FeedResponse(kind=kind, items=[_post_response(post) for post in posts])
    if generation != "uncached":
        await _write_feed_cache(redis, cache_key, response, settings.feed_cache_ttl_seconds)
    return response


@router.get("/health/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


async def _database_ready(request: Request) -> bool:
    try:
        async with request.app.state.session_factory() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=2)
        return True
    except Exception:
        logger.warning("Database readiness check failed", exc_info=True)
        return False


async def _redis_ready(request: Request) -> bool:
    try:
        return bool(await asyncio.wait_for(request.app.state.redis.ping(), timeout=2))
    except Exception:
        logger.warning("Redis readiness check failed", exc_info=True)
        return False


@router.get("/health/ready", response_model=HealthResponse)
@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def ready(request: Request) -> HealthResponse | JSONResponse:
    database, redis = await asyncio.gather(_database_ready(request), _redis_ready(request))
    checks: dict[str, Literal["ok", "error"]] = {
        "database": "ok" if database else "error",
        "redis": "ok" if redis else "error",
    }
    if not all((database, redis)):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=HealthResponse(status="not_ready", checks=checks).model_dump(),
        )
    return HealthResponse(status="ok", checks=checks)
