"""Add likes and follows.

Revision ID: 20260914_0002
Revises: 20260913_0001
Create Date: 2026-09-14 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0002"
down_revision: str | None = "20260913_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "likes",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "post_id"),
    )
    op.create_index("ix_likes_post_id", "likes", ["post_id"], unique=False)
    op.create_table(
        "follows",
        sa.Column("follower_id", sa.String(length=36), nullable=False),
        sa.Column("followed_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("follower_id <> followed_id", name="ck_follows_not_self"),
        sa.ForeignKeyConstraint(["followed_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("follower_id", "followed_id"),
    )
    op.create_index("ix_follows_followed_id", "follows", ["followed_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_follows_followed_id", table_name="follows")
    op.drop_table("follows")
    op.drop_index("ix_likes_post_id", table_name="likes")
    op.drop_table("likes")
