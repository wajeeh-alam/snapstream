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
    assert "What’s happening?" in page.text
    assert "Who to follow" in page.text
    assert styles.status_code == 200
    assert "--blue: #1d9bf0" in styles.text
    assert script.status_code == 200
    assert 'api("/auth/login"' in script.text
    assert 'class="post-column"' in script.text


@pytest.mark.asyncio
async def test_public_capabilities_describe_optional_features(
    test_context: tuple[Any, FakeRedis, FakeS3],
) -> None:
    client, _, _ = test_context

    response = await client.get("/config/public")

    assert response.status_code == 200
    assert response.json() == {
        "public_demo": False,
        "registration_enabled": True,
        "uploads_enabled": True,
    }
