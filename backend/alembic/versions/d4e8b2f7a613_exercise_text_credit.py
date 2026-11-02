"""Credit an exercise's how-to text separately from its artwork.

Revision ID: d4e8b2f7a613
Revises: a7d3c1e5b902
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e8b2f7a613"
down_revision = "a7d3c1e5b902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("exercises", sa.Column("text_license", sa.String(length=40), nullable=True))
    op.add_column("exercises", sa.Column("text_source_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("exercises", "text_source_url")
    op.drop_column("exercises", "text_license")
