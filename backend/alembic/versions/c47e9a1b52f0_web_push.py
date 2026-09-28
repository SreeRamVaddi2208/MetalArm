"""Web Push subscriptions.

Separate from push_devices rather than shoehorned into it: an APNs token is a
short opaque string with a sandbox/production gateway, while a Web Push
subscription is a long endpoint URL plus the two keys its payload is encrypted
with. One table for both would leave half the columns null on every row.

Sits on 8d1f4c60ba57, main's head. The waitlist migration (a3f61d92c485) is on
the marketing-site branch and revises the same parent, so whichever of the two
merges SECOND needs its down_revision repointed at the other - exactly as
4b81c0d5e7a2 did when PR #24 landed first. Alembic sees two heads otherwise.

Revision ID: c47e9a1b52f0
Revises: 8d1f4c60ba57
Create Date: 2026-09-29 10:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c47e9a1b52f0'
down_revision: str | None = '8d1f4c60ba57'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'web_push_subscriptions',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('session_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('p256dh', sa.String(length=200), nullable=False),
        sa.Column('auth', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        # Signing out of a session stops that browser's notifications, which is
        # what the cascade here is for.
        sa.ForeignKeyConstraint(['session_id'], ['auth_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # The endpoint identifies the browser install, not the person: when a
        # second account signs in on the same browser the row MOVES rather than
        # both accounts being notified.
        sa.UniqueConstraint('endpoint', name='uq_web_push_endpoint'),
    )
    op.create_index('ix_web_push_subscriptions_user_id', 'web_push_subscriptions', ['user_id'])
    op.create_index('ix_web_push_subscriptions_session_id', 'web_push_subscriptions', ['session_id'])


def downgrade() -> None:
    op.drop_index('ix_web_push_subscriptions_session_id', table_name='web_push_subscriptions')
    op.drop_index('ix_web_push_subscriptions_user_id', table_name='web_push_subscriptions')
    op.drop_table('web_push_subscriptions')
