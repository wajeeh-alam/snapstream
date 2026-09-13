"""Authentication API tests."""

import hashlib

import pytest

from .conftest import FakeRedis, FakeS3, register_user


@pytest.mark.asyncio
async def test_register_me_login_and_logout(
    test_context: tuple[object, FakeRedis, FakeS3],
) -> None:
    client, redis, _ = test_context
    session = await register_user(client)
    token = session["access_token"]
    digest_key = f"session:{hashlib.sha256(token.encode()).hexdigest()}"

    assert token not in redis.values
    assert redis.values[digest_key] == session["user"]["id"]
    assert redis.expirations[digest_key] == 3600

    me = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"

    login = await client.post(
        "/auth/login",
        json={"login": "ALICE", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"] != token

    logout = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert logout.status_code == 204
    assert digest_key not in redis.values
    rejected = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert rejected.status_code == 401


@pytest.mark.asyncio
async def test_registration_conflicts_and_login_errors(
    test_context: tuple[object, FakeRedis, FakeS3],
) -> None:
    client, _, _ = test_context
    await register_user(client)

    duplicate = await client.post(
        "/auth/register",
        json={
            "email": "other@example.com",
            "username": "ALICE",
            "display_name": "Other Alice",
            "password": "another long password",
        },
    )
    assert duplicate.status_code == 409

    bad_login = await client.post(
        "/auth/login", json={"login": "alice", "password": "incorrect"}
    )
    assert bad_login.status_code == 401
    assert (await client.get("/users/me")).status_code == 401


@pytest.mark.asyncio
async def test_session_backend_failure_returns_service_unavailable(
    test_context: tuple[object, FakeRedis, FakeS3],
) -> None:
    client, redis, _ = test_context
    redis.available = False

    response = await client.get("/users/me", headers={"Authorization": "Bearer opaque"})

    assert response.status_code == 503
