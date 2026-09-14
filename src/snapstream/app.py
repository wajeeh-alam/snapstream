"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import boto3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from .api import router
from .config import Settings, get_settings
from .db import create_engine, create_session_factory

STATIC_DIR = Path(__file__).parent / "static"


def _create_s3_client(settings: Settings, endpoint_url: str | None = None) -> Any:
    kwargs: dict[str, Any] = {
        "region_name": settings.s3_region,
    }
    resolved_endpoint = endpoint_url or settings.s3_endpoint_url
    if resolved_endpoint:
        kwargs["endpoint_url"] = resolved_endpoint
        # LocalStack accepts placeholder credentials and has no task-role endpoint.
        kwargs["aws_access_key_id"] = settings.aws_access_key_id or "test"
        kwargs["aws_secret_access_key"] = (
            settings.aws_secret_access_key.get_secret_value()
            if settings.aws_secret_access_key
            else "test"
        )
    else:
        if settings.aws_access_key_id:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
        if settings.aws_secret_access_key:
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key.get_secret_value()
    return boto3.client("s3", **kwargs)


class _LazyS3Client:
    """Avoid credential-provider network work until an S3 endpoint is used."""

    def __init__(self, settings: Settings, endpoint_url: str | None = None) -> None:
        self.settings = settings
        self.endpoint_url = endpoint_url
        self.client: Any | None = None

    def __getattr__(self, name: str) -> Any:
        if self.client is None:
            self.client = _create_s3_client(self.settings, self.endpoint_url)
        return getattr(self.client, name)


def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | None = None,
    redis_client: Any | None = None,
    s3_client: Any | None = None,
) -> FastAPI:
    """Build an application; injectable clients keep unit tests infrastructure-free."""
    settings = settings or get_settings()
    owned_engine = engine is None
    owned_redis = redis_client is None
    engine = engine or create_engine(settings)
    redis_client = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)
    injected_s3 = s3_client is not None
    s3_client = s3_client or _LazyS3Client(settings)
    s3_presigner = (
        s3_client
        if injected_s3 or not settings.s3_presign_endpoint_url
        else _LazyS3Client(settings, settings.s3_presign_endpoint_url)
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        try:
            if owned_redis:
                await redis_client.aclose()
        finally:
            if owned_engine:
                await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = redis_client
    app.state.s3 = s3_client
    app.state.s3_presigner = s3_presigner
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials="*" not in settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def demo_frontend() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
