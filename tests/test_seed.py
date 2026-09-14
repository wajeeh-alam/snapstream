"""Demo seed primitives are deterministic and dependency-free."""

import struct

from snapstream.seed import DEMO_NAMESPACE, PEOPLE, POSTS, _id, gradient_png


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
