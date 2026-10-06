"""Natural-language set logging: exercise aliases and the parse log.

`exercise_aliases` is seeded by scripts.import_exercises right after the
library, from app/data/exercise_aliases.json. `parse_logs` holds text only.
Neither touches the points ledger: a parse only proposes sets.

Revision ID: 4e8b1c2d9a17
Revises: 32523b4e7c01
Create Date: 2026-10-05 14:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '4e8b1c2d9a17'
down_revision: str | None = '32523b4e7c01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'exercise_aliases',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('exercise_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('alias', sa.String(length=60), nullable=False),
        sa.Column('source', sa.String(length=8), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("source IN ('seed', 'user', 'learned')", name='ck_exercise_aliases_source'),
        sa.CheckConstraint('length(alias) >= 1', name='ck_exercise_aliases_alias'),
        sa.CheckConstraint("(source = 'seed') = (user_id IS NULL)", name='ck_exercise_aliases_owner'),
        sa.UniqueConstraint(
            'alias', 'user_id', name='uq_exercise_aliases_alias', postgresql_nulls_not_distinct=True
        ),
    )
    op.create_index('ix_exercise_aliases_exercise_id', 'exercise_aliases', ['exercise_id'])
    op.create_index('ix_exercise_aliases_user_id', 'exercise_aliases', ['user_id'])

    op.create_table(
        'parse_logs',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('parser_used', sa.String(length=8), nullable=False),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('accepted', sa.Boolean(), nullable=True),
        sa.Column('corrected_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("parser_used IN ('grammar', 'llm', 'none')", name='ck_parse_logs_parser'),
        sa.CheckConstraint('latency_ms >= 0', name='ck_parse_logs_latency'),
    )
    op.create_index('ix_parse_logs_user_time', 'parse_logs', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_parse_logs_user_time', table_name='parse_logs')
    op.drop_table('parse_logs')
    op.drop_index('ix_exercise_aliases_user_id', table_name='exercise_aliases')
    op.drop_index('ix_exercise_aliases_exercise_id', table_name='exercise_aliases')
    op.drop_table('exercise_aliases')
