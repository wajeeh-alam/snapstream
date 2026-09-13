"""Liveness and dependency-aware readiness tests."""

from typing import Any

import pytest

from .conftest import FakeRedis, FakeS3


@pytest.mark.asyncio
async def test_liveness_and_readiness(
    test_context: tuple[Any, FakeRedis, FakeS3],
) -> None:
    client, redis, _ = test_context

    live = await client.get("/health/live")
    ready = await client.get("/health/ready")
    compatibility = await client.get("/health")

    assert live.status_code == 200
    assert live.json() == {"status": "ok", "checks": None}
    assert ready.status_code == 200
    assert ready.json()["checks"] == {"database": "ok", "redis": "ok"}
    assert compatibility.status_code == 200

    redis.available = False
    not_ready = await client.get("/health/ready")
    assert not_ready.status_code == 503
    assert not_ready.json() == {
        "status": "not_ready",
        "checks": {"database": "ok", "redis": "error"},
    }
