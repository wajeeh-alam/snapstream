"""Infrastructure-free test doubles and application fixtures."""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest_asyncio
from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import create_async_engine

from snapstream.app import create_app
from snapstream.config import Settings
from snapstream.models import Base


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}
        self.set_calls: list[str] = []
        self.available = True

    def _check(self) -> None:
        if not self.available:
            raise ConnectionError("redis unavailable")

    async def get(self, key: str) -> str | None:
        self._check()
        return self.values.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None) -> bool:
        self._check()
        self.values[key] = str(value)
        self.set_calls.append(key)
        if ex is not None:
            self.expirations[key] = ex
        return True

    async def delete(self, key: str) -> int:
        self._check()
        existed = key in self.values
        self.values.pop(key, None)
        return int(existed)

    async def incr(self, key: str) -> int:
        self._check()
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value

    async def ping(self) -> bool:
        self._check()
        return True


class FakeS3:
    def __init__(self) -> None:
        self.presign_calls: list[dict[str, Any]] = []
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}

    def generate_presigned_url(self, operation: str, **kwargs: Any) -> str:
        self.presign_calls.append({"operation": operation, **kwargs})
        return f"https://s3.test/{kwargs['Params']['Key']}?signed=true"

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        try:
            return self.objects[(Bucket, Key)]
        except KeyError as exc:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "missing"}},
                "HeadObject",
            ) from exc


@pytest_asyncio.fixture
async def test_context() -> AsyncIterator[tuple[httpx.AsyncClient, FakeRedis, FakeS3]]:
    settings = Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite://",
        redis_url="redis://unused",
        s3_bucket="snapstream-test",
        session_ttl_seconds=3600,
        feed_cache_ttl_seconds=7,
        max_media_size_bytes=1024,
    )
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    redis = FakeRedis()
    s3 = FakeS3()
    app = create_app(settings, engine=engine, redis_client=redis, s3_client=s3)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, redis, s3
    await engine.dispose()


async def register_user(
    client: httpx.AsyncClient,
    *,
    username: str = "alice",
    email: str = "alice@example.com",
) -> dict[str, Any]:
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "username": username,
            "display_name": username.title(),
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
