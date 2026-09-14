"""Create deterministic, fictional demo content for local SnapStream environments."""

from __future__ import annotations

import argparse
import asyncio
import os
import struct
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from sqlalchemy import delete, func, select

from .app import _create_s3_client
from .config import Settings
from .db import create_engine, create_session_factory
from .models import Follow, Like, Post, User
from .security import hash_password

DEMO_NAMESPACE = UUID("88b6bc7e-5d0b-4210-9906-c6e1afaa73c7")


@dataclass(frozen=True)
class DemoPerson:
    username: str
    display_name: str
    color: tuple[int, int, int]
    accent: tuple[int, int, int]


PEOPLE = (
    DemoPerson("maya_frames", "Maya Chen", (236, 105, 91), (255, 205, 112)),
    DemoPerson("noah_trails", "Noah Williams", (42, 139, 160), (111, 212, 167)),
    DemoPerson("lina_builds", "Lina Haddad", (103, 78, 167), (221, 119, 171)),
    DemoPerson("theo_tastes", "Theo Martin", (222, 111, 70), (248, 192, 91)),
    DemoPerson("zoe_afterdark", "Zoë Alvarez", (44, 46, 77), (150, 102, 255)),
    DemoPerson("sam_onfilm", "Sam Okafor", (47, 111, 91), (132, 211, 143)),
    DemoPerson("priya_pixels", "Priya Rao", (202, 73, 108), (241, 160, 119)),
    DemoPerson("eli.weekends", "Eli Brooks", (50, 96, 158), (116, 180, 235)),
)

POSTS = (
    (0, "Golden hour found us before the rain did.", True),
    (1, "Six quiet miles, one very loud waterfall.", True),
    (2, "The tiny accessibility detail that made today's build feel finished.", False),
    (3, "Sunday experiment: citrus, charred scallions, and zero leftovers.", True),
    (4, "The city changes character after the last train.", True),
    (5, "Shot a whole roll looking for this exact shade of green.", True),
    (6, "Color study: warm shadows, cold type, happy accident.", True),
    (7, "A lake, a paperback, and absolutely no notifications.", True),
    (0, "A five-minute walk that turned into an entire afternoon.", True),
    (2, "Shipped the feed interaction states. The optimistic heart wins.", False),
    (3, "There is no such thing as too much lemon zest.", True),
    (1, "Trail rule: take the photo, then put the phone away.", True),
    (6, "Found a type pairing I want to use on everything now.", True),
    (5, "Morning market portraits, developed at home.", True),
    (4, "Blue hour lasted eleven minutes. Worth the wait.", True),
    (7, "Weekend forecast: windows down, maps optional.", True),
    (0, "Proof that ordinary corners can still surprise you.", True),
    (3, "The crispy edge is the whole point.", True),
    (2, "Small systems compound: one reusable component at a time.", False),
    (5, "Grain, motion, and a little bit of luck.", True),
    (1, "The view from 1,400 metres made the early alarm negotiable.", True),
    (6, "Poster draft three finally has room to breathe.", True),
    (4, "Late coffee, wet pavement, neon reflections.", True),
    (7, "Saved this one for when the week needed more horizon.", True),
)


def _id(kind: str, name: str) -> str:
    return str(uuid5(DEMO_NAMESPACE, f"{kind}:{name}"))


def gradient_png(
    width: int,
    height: int,
    start: tuple[int, int, int],
    end: tuple[int, int, int],
) -> bytes:
    """Create a compact RGB gradient PNG using only the standard library."""
    rows = bytearray()
    denominator = max(width + height - 2, 1)
    for y in range(height):
        rows.append(0)
        for x in range(width):
            mix = (x + y) / denominator
            vignette = 0.86 + 0.14 * (1 - abs(x / max(width - 1, 1) - 0.5) * 2)
            rows.extend(
                min(255, round((start[channel] * (1 - mix) + end[channel] * mix) * vignette))
                for channel in range(3)
            )

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + chunk(b"IEND", b"")
    )


async def seed_demo(settings: Settings, password: str, *, reset: bool = False) -> dict[str, int]:
    if settings.environment.lower() not in {"development", "local", "test"}:
        raise RuntimeError("demo seeding is disabled outside development/local/test")

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    user_ids = [_id("user", person.username) for person in PEOPLE]
    post_ids = [_id("post", str(index)) for index in range(len(POSTS))]
    password_hash = await asyncio.to_thread(hash_password, password)
    s3 = _create_s3_client(settings) if settings.s3_bucket else None
    now = datetime.now(UTC)

    try:
        async with session_factory() as db:
            if reset:
                await db.execute(delete(User).where(User.id.in_(user_ids)))
                await db.commit()

            for index, person in enumerate(PEOPLE):
                user = await db.get(User, user_ids[index])
                if user is None:
                    user = User(
                        id=user_ids[index],
                        email=f"{person.username}@snapstream.demo",
                        username=person.username,
                        display_name=person.display_name,
                        password_hash=password_hash,
                        created_at=now - timedelta(days=90 - index * 4),
                    )
                    db.add(user)
                else:
                    user.password_hash = password_hash
                    user.display_name = person.display_name
            await db.commit()

            for index, (author_index, body, has_media) in enumerate(POSTS):
                if await db.get(Post, post_ids[index]) is not None:
                    continue
                person = PEOPLE[author_index]
                media_key = None
                media_size = None
                if has_media and s3 is not None:
                    image = gradient_png(720, 450, person.color, person.accent)
                    media_key = f"uploads/{user_ids[author_index]}/demo-{index + 1:02d}.png"
                    await asyncio.to_thread(
                        s3.put_object,
                        Bucket=settings.s3_bucket,
                        Key=media_key,
                        Body=image,
                        ContentType="image/png",
                        Metadata={"owner-id": user_ids[author_index]},
                        ServerSideEncryption="AES256",
                    )
                    media_size = len(image)
                db.add(
                    Post(
                        id=post_ids[index],
                        author_id=user_ids[author_index],
                        body=body,
                        media_bucket=settings.s3_bucket if media_key else None,
                        media_key=media_key,
                        media_content_type="image/png" if media_key else None,
                        media_size_bytes=media_size,
                        created_at=now - timedelta(hours=index * 3 + 1),
                    )
                )
            await db.commit()

            await db.execute(delete(Like).where(Like.user_id.in_(user_ids)))
            await db.execute(delete(Follow).where(Follow.follower_id.in_(user_ids)))
            for user_index, user_id in enumerate(user_ids):
                for post_index, post_id in enumerate(post_ids):
                    author_index = POSTS[post_index][0]
                    if author_index != user_index and (post_index * 3 + user_index) % 7 < 3:
                        db.add(Like(user_id=user_id, post_id=post_id))
                for target_index, target_id in enumerate(user_ids):
                    if target_id != user_id and (target_index + user_index * 2) % 3 == 0:
                        db.add(Follow(follower_id=user_id, followed_id=target_id))
            await db.flush()
            for post_id in post_ids:
                count = await db.scalar(
                    select(func.count()).select_from(Like).where(Like.post_id == post_id)
                )
                post = await db.get(Post, post_id)
                if post is not None:
                    post.likes_count = int(count or 0)
            await db.commit()
    finally:
        await engine.dispose()

    return {"users": len(user_ids), "posts": len(post_ids)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="replace existing demo records")
    args = parser.parse_args()
    password = os.environ.get("DEMO_PASSWORD")
    if not password or len(password) < 8:
        parser.error("DEMO_PASSWORD must be set to at least 8 characters")
    result = asyncio.run(seed_demo(Settings(), password, reset=args.reset))
    print(f"Seeded {result['users']} fictional users and {result['posts']} posts.")
    print(f"Demo login: {PEOPLE[0].username} (password from DEMO_PASSWORD)")


if __name__ == "__main__":
    main()
