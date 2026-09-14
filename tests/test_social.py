"""Like, follow, discovery, and media download API tests."""

from typing import Any

import pytest

from .conftest import FakeRedis, FakeS3, register_user


@pytest.mark.asyncio
async def test_like_and_unlike_are_idempotent_and_invalidate_feed(
    test_context: tuple[Any, FakeRedis, FakeS3],
) -> None:
    client, redis, _ = test_context
    alice = await register_user(client)
    bob = await register_user(client, username="bob", email="bob@example.com")
    alice_auth = {"Authorization": f"Bearer {alice['access_token']}"}
    bob_auth = {"Authorization": f"Bearer {bob['access_token']}"}
    post = (await client.post("/posts", headers=alice_auth, json={"body": "Hi"})).json()

    first = await client.post(f"/posts/{post['id']}/likes", headers=bob_auth)
    repeated = await client.post(f"/posts/{post['id']}/likes", headers=bob_auth)
    assert first.json() == {"post_id": post["id"], "likes_count": 1, "liked": True}
    assert repeated.json() == first.json()

    removed = await client.delete(f"/posts/{post['id']}/likes", headers=bob_auth)
    repeated_remove = await client.delete(f"/posts/{post['id']}/likes", headers=bob_auth)
    assert removed.json() == {"post_id": post["id"], "likes_count": 0, "liked": False}
    assert repeated_remove.json() == removed.json()
    assert redis.values["feed:generation"] == "3"


@pytest.mark.asyncio
async def test_follow_unfollow_and_user_discovery(
    test_context: tuple[Any, FakeRedis, FakeS3],
) -> None:
    client, _, _ = test_context
    alice = await register_user(client)
    bob = await register_user(client, username="bob", email="bob@example.com")
    auth = {"Authorization": f"Bearer {alice['access_token']}"}

    users = await client.get("/users")
    assert [user["username"] for user in users.json()] == ["alice", "bob"]
    followed = await client.post(f"/users/{bob['user']['id']}/follow", headers=auth)
    repeated = await client.post(f"/users/{bob['user']['id']}/follow", headers=auth)
    assert followed.json() == {"user_id": bob["user"]["id"], "following": True}
    assert repeated.json() == followed.json()
    unfollowed = await client.delete(f"/users/{bob['user']['id']}/follow", headers=auth)
    assert unfollowed.json()["following"] is False
    self_follow = await client.post(f"/users/{alice['user']['id']}/follow", headers=auth)
    assert self_follow.status_code == 422


@pytest.mark.asyncio
async def test_media_url_is_short_lived_and_missing_media_is_404(
    test_context: tuple[Any, FakeRedis, FakeS3],
) -> None:
    client, _, s3 = test_context
    alice = await register_user(client)
    auth = {"Authorization": f"Bearer {alice['access_token']}"}
    key = f"uploads/{alice['user']['id']}/photo.png"
    s3.objects[("snapstream-test", key)] = {
        "ContentLength": 12,
        "ContentType": "image/png",
        "Metadata": {"owner-id": alice["user"]["id"]},
    }
    post = (
        await client.post(
            "/posts",
            headers=auth,
            json={
                "body": "A photo",
                "media": {"key": key, "content_type": "image/png", "size_bytes": 12},
            },
        )
    ).json()

    response = await client.get(f"/posts/{post['id']}/media-url")
    assert response.status_code == 200
    assert response.json()["expires_in"] == 900
    assert response.json()["download_url"].startswith("https://s3.test/")
    assert s3.presign_calls[-1]["operation"] == "get_object"
    missing = await client.get("/posts/does-not-exist/media-url")
    assert missing.status_code == 404
