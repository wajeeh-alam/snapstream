"""The zero-build demo frontend is bundled with the API."""

from typing import Any

import pytest

from .conftest import FakeRedis, FakeS3


@pytest.mark.asyncio
async def test_frontend_and_assets_are_served(
    test_context: tuple[Any, FakeRedis, FakeS3],
) -> None:
    client, _, _ = test_context
    page = await client.get("/")
    styles = await client.get("/static/styles.css")
    script = await client.get("/static/app.js")

    assert page.status_code == 200
    assert "Small moments" in page.text
    assert styles.status_code == 200
    assert "--coral" in styles.text
    assert script.status_code == 200
    assert 'api("/auth/login"' in script.text
