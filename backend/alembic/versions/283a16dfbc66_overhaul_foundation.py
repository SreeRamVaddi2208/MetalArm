"""Overhaul phase 0: profile fields, the exercise taxonomy, exercise media.

- users: username (+ a lowercased copy carrying the UNIQUE), avatar_url, bio,
  default_rest_seconds, default_visibility. All nullable or defaulted, so no
  existing row needs touching.
- muscle_groups / equipment: display names and artwork for the codes
  exercises already store (workout_enums). Seeded by scripts.import_exercises.
- exercises: secondary muscles, mechanic, numbered steps and tips, and library
  artwork with its licence and author (most of it CC-BY-SA). The existing
  free-text instructions become each exercise's first step, so the detail
  screen has something to show before richer data is imported.

Revision ID: 283a16dfbc66
Revises: 7a3e9f0b5c42
Create Date: 2026-10-06 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '283a16dfbc66'
down_revision: str | None = '7a3e9f0b5c42'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MUSCLES = (
    "'chest', 'back', 'lats', 'traps', 'shoulders', 'biceps', 'triceps', 'forearms', 'abs',"
    " 'obliques', 'lower_back', 'glutes', 'quads', 'hamstrings', 'calves', 'adductors',"
    " 'abductors', 'neck', 'full_body', 'cardio'"
)
EQUIPMENT = (
    "'barbell', 'dumbbell', 'machine', 'cable', 'kettlebell', 'bodyweight', 'band',"
    " 'smith_machine', 'ez_bar', 'trap_bar', 'plate', 'cardio_machine', 'other'"
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    ]


def upgrade() -> None:
    op.add_column('users', sa.Column('username', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('username_normalized', sa.String(length=30), nullable=True))
    op.create_unique_constraint('users_username_normalized_key', 'users', ['username_normalized'])
    op.add_column('users', sa.Column('avatar_url', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('bio', sa.String(length=160), nullable=True))
    op.add_column('users', sa.Column('default_rest_seconds', sa.Integer(), server_default='90', nullable=False))
    op.add_column('users', sa.Column('default_visibility', sa.String(length=10), server_default='followers', nullable=False))
    op.create_check_constraint(
        'ck_users_default_visibility', 'users', "default_visibility IN ('public', 'followers', 'private')"
    )
    op.create_check_constraint(
        'ck_users_default_rest', 'users', 'default_rest_seconds >= 0 AND default_rest_seconds <= 900'
    )
    op.create_check_constraint(
        'ck_users_username', 'users',
        "username_normalized IS NULL OR username_normalized ~ '^[a-z0-9_.]{3,30}$'",
    )

    op.create_table(
        'muscle_groups',
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('display_name', sa.String(length=40), nullable=False),
        sa.Column('body_side', sa.String(length=8), nullable=False),
        sa.Column('svg_path_ids', postgresql.ARRAY(sa.String(length=40)), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('size_class', sa.String(length=8), nullable=False),
        sa.Column('tile_asset', sa.String(length=80), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('browsable', sa.Boolean(), server_default='true', nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('code'),
        sa.CheckConstraint(f"code IN ({MUSCLES})", name='ck_muscle_groups_code'),
        sa.CheckConstraint("body_side IN ('front', 'back', 'both', 'none')", name='ck_muscle_groups_side'),
        sa.CheckConstraint("size_class IN ('small', 'large')", name='ck_muscle_groups_size'),
    )
    op.create_table(
        'equipment',
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('display_name', sa.String(length=40), nullable=False),
        sa.Column('icon_asset', sa.String(length=80), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('browsable', sa.Boolean(), server_default='true', nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('code'),
        sa.CheckConstraint(f"code IN ({EQUIPMENT})", name='ck_equipment_code'),
    )

    op.add_column('exercises', sa.Column(
        'secondary_muscle_groups', postgresql.ARRAY(sa.String(length=32)),
        server_default=sa.text("'{}'"), nullable=False))
    op.add_column('exercises', sa.Column('mechanic', sa.String(length=10), nullable=True))
    op.add_column('exercises', sa.Column('steps', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False))
    op.add_column('exercises', sa.Column('tips', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False))
    for column in ('thumbnail_url', 'illustration_url', 'animation_url', 'media_source_url'):
        op.add_column('exercises', sa.Column(column, sa.String(length=500), nullable=True))
    op.add_column('exercises', sa.Column('media_license', sa.String(length=40), nullable=True))
    op.add_column('exercises', sa.Column('media_author', sa.String(length=200), nullable=True))
    op.create_check_constraint(
        'ck_exercises_secondary_muscles', 'exercises',
        f"secondary_muscle_groups <@ ARRAY[{MUSCLES}]::varchar[]",
    )
    op.create_check_constraint(
        'ck_exercises_mechanic', 'exercises', "mechanic IS NULL OR mechanic IN ('compound', 'isolation')"
    )
    op.create_check_constraint(
        'ck_exercises_media_attribution', 'exercises',
        "(thumbnail_url IS NULL AND illustration_url IS NULL AND animation_url IS NULL)"
        " OR (media_license IS NOT NULL AND media_author IS NOT NULL)",
    )
    op.execute(
        "UPDATE exercises SET steps = ARRAY[instructions] "
        "WHERE instructions IS NOT NULL AND instructions <> ''"
    )


def downgrade() -> None:
    for name in ('ck_exercises_media_attribution', 'ck_exercises_mechanic', 'ck_exercises_secondary_muscles'):
        op.drop_constraint(name, 'exercises', type_='check')
    for column in ('media_author', 'media_license', 'media_source_url', 'animation_url',
                   'illustration_url', 'thumbnail_url', 'tips', 'steps', 'mechanic',
                   'secondary_muscle_groups'):
        op.drop_column('exercises', column)
    op.drop_table('equipment')
    op.drop_table('muscle_groups')
    for name in ('ck_users_username', 'ck_users_default_rest', 'ck_users_default_visibility'):
        op.drop_constraint(name, 'users', type_='check')
    op.drop_constraint('users_username_normalized_key', 'users', type_='unique')
    for column in ('default_visibility', 'default_rest_seconds', 'bio', 'avatar_url',
                   'username_normalized', 'username'):
        op.drop_column('users', column)
