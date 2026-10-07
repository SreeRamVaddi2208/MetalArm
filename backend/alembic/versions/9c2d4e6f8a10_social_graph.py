"""Overhaul phase 4: follows, reactions, notifications.

Revision ID: 9c2d4e6f8a10
Revises: 53f6a8cbeda0
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = "9c2d4e6f8a10"
down_revision = "53f6a8cbeda0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "follows",
        sa.Column("follower_id", sa.Uuid(), nullable=False),
        sa.Column("followee_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("follower_id <> followee_id", name="ck_follows_not_self"),
        sa.ForeignKeyConstraint(["followee_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("follower_id", "followee_id"),
    )
    op.create_index("ix_follows_followee", "follows", ["followee_id", "follower_id"])
    op.create_table(
        "reactions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=16), server_default="spotted", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("type IN ('spotted')", name="ck_reactions_type"),
        sa.ForeignKeyConstraint(["session_id"], ["workout_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "session_id", "type", name="uq_reactions_once"),
    )
    op.create_index("ix_reactions_session", "reactions", ["session_id"])
    op.create_table(
        "notifications",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("target_type", sa.String(length=16), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("detail", sa.String(length=160), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "type IN ('follow', 'reaction', 'duel_challenge', 'friend_pr', 'quest_complete')",
            name="ck_notifications_type"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.create_index("ix_notifications_actor", "notifications", ["actor_user_id"])
    op.create_index("ix_notifications_unread", "notifications", ["user_id"],
                    postgresql_where=sa.text("read_at IS NULL"))


def downgrade() -> None:
    op.drop_index("ix_notifications_unread", table_name="notifications")
    op.drop_index("ix_notifications_actor", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_reactions_session", table_name="reactions")
    op.drop_table("reactions")
    op.drop_index("ix_follows_followee", table_name="follows")
    op.drop_table("follows")
