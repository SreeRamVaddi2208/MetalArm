"""Create the pg_stat_statements extension.

Without it there is no per-statement view of the database at all: you can see
that something is slow and not which query it was. Every later decision about
what to optimise cites this view, so it has to exist first.

The extension and the library are two halves of one feature. The LIBRARY has to
be preloaded at server start (shared_preload_libraries, set in the compose files
and by the provider on a managed database); the EXTENSION has to be created per
database, which is what this does. Creating it without the library preloaded
succeeds and leaves a view that errors when queried - so the compose change and
this migration belong to each other.

IF NOT EXISTS because several managed providers ship it already created.

Revision ID: c1a5f8d3b620
Revises: b7e4a2c91d35
Create Date: 2026-09-30 11:40:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = 'c1a5f8d3b620'
down_revision: str | None = 'b7e4a2c91d35'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")


def downgrade() -> None:
    # Dropping it discards the statistics collected so far, which is the whole
    # value of having had it. Harmless either way: it holds no application data.
    op.execute("DROP EXTENSION IF EXISTS pg_stat_statements")
