"""user token version

Adds users.token_version, bumped to revoke every token already issued (sign
out everywhere). The server default of 0 matches tokens minted before this
column existed: they carry no `tv` claim, which is read as 0, so deploying this
does not sign anyone out.

Revision ID: 7b3e9d41c2a8
Revises: 2caadc5c9d12
Create Date: 2026-09-13 22:15:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '7b3e9d41c2a8'
down_revision: str | None = '2caadc5c9d12'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('token_version', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'token_version')
