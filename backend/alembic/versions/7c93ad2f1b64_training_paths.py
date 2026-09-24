"""training paths

`users.character_class` - powerlifter / bodybuilder / athlete - used to be
cosmetic: it decided which character-sheet stats were highlighted. It is now the
user's TRAINING PATH, chosen during onboarding, so this adds:

- `users.character_class_set_at`, to tell "never asked" from "asked and
  cleared" (onboarding must not keep asking someone who declined), and
- `training_category_profiles`, what each path MEANS - rep range, load, volume,
  rest and the tags saying which exercises suit it. In a table because those are
  tuning values, editable and readable by both clients without a release.

Seeded here from app/data/training_categories.json so an upgraded database has
the paths immediately; app/core/training_categories.seed() re-runs on deploy.

No existing value changes: the three stored strings stay exactly as they were.

Revision ID: 7c93ad2f1b64
Revises: 4b81c0d5e7a2
Create Date: 2026-09-20 21:10:00.000000
"""

import json
from collections.abc import Sequence
from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision: str = '7c93ad2f1b64'
down_revision: str | None = '4b81c0d5e7a2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DATA = Path(__file__).resolve().parents[2] / "app" / "data" / "training_categories.json"


def upgrade() -> None:
    op.add_column(
        'users', sa.Column('character_class_set_at', sa.DateTime(timezone=True), nullable=True)
    )
    profiles = op.create_table(
        'training_category_profiles',
        sa.Column('category', sa.String(length=16), nullable=False),
        sa.Column('display_name', sa.String(length=40), nullable=False),
        sa.Column('tagline', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('rep_range_low', sa.Integer(), nullable=False),
        sa.Column('rep_range_high', sa.Integer(), nullable=False),
        sa.Column('relative_load', sa.String(length=16), nullable=False),
        sa.Column('relative_volume', sa.String(length=16), nullable=False),
        sa.Column('rest_seconds_guidance', sa.Integer(), nullable=False),
        sa.Column('emphasis_tags', sa.ARRAY(sa.String(length=32)), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "category IN ('powerlifter', 'bodybuilder', 'athlete')",
            name='ck_training_categories_category',
        ),
        sa.CheckConstraint(
            'rep_range_low >= 1 AND rep_range_low <= rep_range_high',
            name='ck_training_categories_rep_range',
        ),
        sa.CheckConstraint(
            'rest_seconds_guidance >= 0 AND rest_seconds_guidance <= 3600',
            name='ck_training_categories_rest',
        ),
        sa.CheckConstraint(
            "relative_load IN ('low', 'moderate', 'moderate_high', 'heavy')",
            name='ck_training_categories_load',
        ),
        sa.CheckConstraint(
            "relative_volume IN ('low', 'moderate', 'moderate_high', 'high')",
            name='ck_training_categories_volume',
        ),
        sa.PrimaryKeyConstraint('category'),
    )
    op.bulk_insert(profiles, json.loads(_DATA.read_text()))


def downgrade() -> None:
    op.drop_table('training_category_profiles')
    op.drop_column('users', 'character_class_set_at')
