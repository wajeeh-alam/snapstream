"""FastAPI dependencies shared by API routes."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .models import User
from .security import session_digest

bearer_scheme = HTTPBearer(auto_error=False)


def get_redis(request: Request) -> Any:
    return request.app.state.redis


def get_s3(request: Request) -> Any:
    return request.app.state.s3


def get_s3_presigner(request: Request) -> Any:
    return request.app.state.s3_presigner


def get_app_settings(request: Request) -> Any:
    return request.app.state.settings


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Any, Depends(get_redis)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid or expired bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        user_id = await redis.get(f"session:{session_digest(credentials.credentials)}")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="session service unavailable",
        ) from exc
    if not user_id:
        raise unauthorized
    if isinstance(user_id, bytes):
        user_id = user_id.decode()
    user = await db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user
