"""The marketing site's waitlist.

One small table. Not part of users: somebody on the waitlist has no account,
and modelling them as a half-user would mean a row that can never log in.

Revision ID: a3f61d92c485
Revises: 8d1f4c60ba57
Create Date: 2026-09-26 11:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f61d92c485'
down_revision: str | None = '8d1f4c60ba57'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'waitlist_entries',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('source', sa.String(length=40), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        # Joining twice is idempotent rather than an error, and the UNIQUE is
        # what makes that true under concurrency.
        sa.UniqueConstraint('email', name='uq_waitlist_email'),
    )


def downgrade() -> None:
    op.drop_table('waitlist_entries')
