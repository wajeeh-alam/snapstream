"""Upload, post persistence, and Redis feed-cache tests."""

from typing import Any

import pytest

from .conftest import FakeRedis, FakeS3, register_user


@pytest.mark.asyncio
async def test_presign_validates_media_and_signs_private_put_headers(
    test_context: tuple[Any, FakeRedis, FakeS3],
) -> None:
    client, _, s3 = test_context
    session = await register_user(client)
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    response = await client.post(
        "/uploads/presign",
        headers=headers,
        json={"filename": "photo.exe", "content_type": "image/jpeg", "size_bytes": 512},
    )

    assert response.status_code == 201
    upload = response.json()
    assert upload["method"] == "PUT"
    assert upload["key"].startswith(f"uploads/{session['user']['id']}/")
    assert upload["key"].endswith(".jpg")
    assert upload["headers"]["Content-Length"] == "512"
    assert upload["headers"]["x-amz-server-side-encryption"] == "AES256"
    params = s3.presign_calls[0]["Params"]
    assert params["Bucket"] == "snapstream-test"
    assert params["Metadata"] == {"owner-id": session["user"]["id"]}
    assert "ACL" not in params

    too_large = await client.post(
        "/uploads/presign",
        headers=headers,
        json={"filename": "x.mp4", "content_type": "video/mp4", "size_bytes": 1025},
    )
    unsupported = await client.post(
        "/uploads/presign",
        headers=headers,
        json={"filename": "x.svg", "content_type": "image/svg+xml", "size_bytes": 10},
    )
    assert too_large.status_code == 422
    assert unsupported.status_code == 422


@pytest.mark.asyncio
async def test_post_stores_only_verified_s3_metadata_and_invalidates_feed(
    test_context: tuple[Any, FakeRedis, FakeS3],
) -> None:
    client, redis, s3 = test_context
    session = await register_user(client)
    auth = {"Authorization": f"Bearer {session['access_token']}"}
    presigned = (
        await client.post(
            "/uploads/presign",
            headers=auth,
            json={"filename": "clip.mp4", "content_type": "video/mp4", "size_bytes": 800},
        )
    ).json()
    s3.objects[(presigned["bucket"], presigned["key"])] = {
        "ContentLength": 800,
        "ContentType": "video/mp4",
        "Metadata": {"owner-id": session["user"]["id"]},
        "Body": b"this value must never enter the database response",
    }

    created = await client.post(
        "/posts",
        headers=auth,
        json={
            "body": "First post",
            "media": {
                "key": presigned["key"],
                "content_type": "video/mp4",
                "size_bytes": 800,
            },
        },
    )

    assert created.status_code == 201, created.text
    assert created.json()["media"] == {
        "bucket": "snapstream-test",
        "key": presigned["key"],
        "content_type": "video/mp4",
        "size_bytes": 800,
    }
    assert "Body" not in created.text
    assert redis.values["feed:generation"] == "1"

    recent = await client.get("/feed", params={"kind": "recent", "limit": 10})
    assert recent.status_code == 200
    assert recent.json()["items"][0]["body"] == "First post"
    feed_cache_keys = [key for key in redis.values if key.startswith("feed:1:recent:10")]
    assert feed_cache_keys
    assert redis.expirations[feed_cache_keys[0]] == 7

    second = await client.post("/posts", headers=auth, json={"body": "Second post"})
    assert second.status_code == 201
    assert redis.values["feed:generation"] == "2"
    refreshed = await client.get("/feed", params={"kind": "recent", "limit": 10})
    assert [item["body"] for item in refreshed.json()["items"]] == [
        "Second post",
        "First post",
    ]


@pytest.mark.asyncio
async def test_post_rejects_unverified_or_cross_user_media(
    test_context: tuple[Any, FakeRedis, FakeS3],
) -> None:
    client, _, s3 = test_context
    alice = await register_user(client)
    bob = await register_user(client, username="bob", email="bob@example.com")
    alice_id = alice["user"]["id"]
    key = f"uploads/{alice_id}/asset.jpg"
    s3.objects[("snapstream-test", key)] = {
        "ContentLength": 100,
        "ContentType": "image/jpeg",
        "Metadata": {"owner-id": alice_id},
    }

    response = await client.post(
        "/posts",
        headers={"Authorization": f"Bearer {bob['access_token']}"},
        json={
            "media": {"key": key, "content_type": "image/jpeg", "size_bytes": 100}
        },
    )
    missing = await client.post(
        "/posts",
        headers={"Authorization": f"Bearer {alice['access_token']}"},
        json={
            "media": {
                "key": f"uploads/{alice_id}/missing.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 100,
            }
        },
    )

    assert response.status_code == 422
    assert missing.status_code == 422


@pytest.mark.asyncio
async def test_feed_falls_back_to_database_when_cache_is_down(
    test_context: tuple[Any, FakeRedis, FakeS3],
) -> None:
    client, redis, _ = test_context
    session = await register_user(client)
    auth = {"Authorization": f"Bearer {session['access_token']}"}
    created = await client.post("/posts", headers=auth, json={"body": "available"})
    assert created.status_code == 201
    redis.available = False

    response = await client.get("/feed", params={"kind": "trending"})

    assert response.status_code == 200
    assert response.json()["kind"] == "trending"
    assert response.json()["items"][0]["body"] == "available"
