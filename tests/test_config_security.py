"""Settings compatibility and security primitive tests."""

from snapstream.config import Settings
from snapstream.security import hash_password, new_session_token, session_digest, verify_password


def test_deployment_environment_aliases(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db/snapstream")
    monkeypatch.setenv("AWS_REGION", "ca-central-1")
    monkeypatch.setenv("AWS_ENDPOINT_URL", "")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "2048")
    monkeypatch.setenv("CORS_ORIGINS", "https://one.test,https://two.test")

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.s3_region == "ca-central-1"
    assert settings.s3_endpoint_url is None
    assert settings.max_media_size_bytes == 2048
    assert settings.cors_origins == ["https://one.test", "https://two.test"]


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("strong password")
    second = hash_password("strong password")

    assert first != second
    assert verify_password("strong password", first)
    assert not verify_password("wrong password", first)
    assert not verify_password("strong password", "malformed")


def test_session_tokens_are_opaque_and_digest_deterministically() -> None:
    first = new_session_token()
    second = new_session_token()

    assert first != second
    assert len(first) >= 40
    assert session_digest(first) == session_digest(first)
    assert first not in session_digest(first)
