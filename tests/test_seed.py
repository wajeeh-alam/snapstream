"""Demo seed primitives are deterministic and dependency-free."""

import struct

import pytest

from snapstream.config import Settings
from snapstream.seed import (
    DEMO_NAMESPACE,
    PEOPLE,
    POSTS,
    _id,
    ensure_demo_seed_allowed,
    gradient_png,
)


def test_demo_identifiers_and_content_are_stable() -> None:
    assert len(PEOPLE) == 8
    assert len(POSTS) == 24
    assert _id("user", PEOPLE[0].username) == _id("user", PEOPLE[0].username)
    assert _id("user", PEOPLE[0].username) != _id("post", PEOPLE[0].username)
    assert str(DEMO_NAMESPACE) not in {person.username for person in PEOPLE}


def test_gradient_png_has_valid_signature_and_dimensions() -> None:
    image = gradient_png(12, 7, (10, 20, 30), (200, 210, 220))
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">II", image[16:24]) == (12, 7)
    assert image.endswith(b"IEND\xaeB`\x82")


def test_production_seed_requires_all_demo_guards() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        demo_seed_enabled=True,
        database_url="postgresql+asyncpg://user:pass@db/snapstream_demo",
    )

    with pytest.raises(RuntimeError, match="--allow-production-demo"):
        ensure_demo_seed_allowed(settings, allow_production_demo=False)

    ensure_demo_seed_allowed(settings, allow_production_demo=True)


def test_production_seed_rejects_non_demo_database() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        demo_seed_enabled=True,
        database_url="postgresql+asyncpg://user:pass@db/production",
    )

    with pytest.raises(RuntimeError, match="snapstream_demo"):
        ensure_demo_seed_allowed(settings, allow_production_demo=True)
