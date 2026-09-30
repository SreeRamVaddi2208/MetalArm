"""Indexes the schema cannot afford to be missing.

Asserted against the real schema in Postgres rather than by reading the model
files, because what matters is what the planner can use. conftest builds the
test database with Base.metadata.create_all, so these describe the models - and
`alembic check` separately proves the models and the migrations agree.

The foreign-key test is the durable one: Postgres indexes the referenced side of
a foreign key automatically and the referencing side not at all, so it is very
easy to add a relationship and quietly turn a delete into a sequential scan.
Five had accumulated before anyone looked.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

# Leading-column coverage only. An index on (boss_id, session_id) does NOT help
# a foreign key on session_id - the planner cannot start a scan in the middle of
# a composite key - which is exactly how raid_hits.session_id was missed.
UNINDEXED_FOREIGN_KEYS = text(
    """
    SELECT c.conrelid::regclass::text AS child_table,
           a.attname                  AS fk_column,
           c.confrelid::regclass::text AS parent_table
    FROM pg_constraint c
    JOIN unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord) ON true
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
    WHERE c.contype = 'f'
      AND k.ord = 1
      AND NOT EXISTS (
        SELECT 1 FROM pg_index i
        WHERE i.indrelid = c.conrelid
          AND i.indkey[0] = k.attnum
      )
    ORDER BY 1, 2
    """
)


def test_every_foreign_key_has_a_supporting_index(engine: Engine):
    """A parent delete must never seq-scan the child.

    If this fails, the named column needs `index=True`, or a composite index
    that LEADS with it. The consequence of ignoring it is that an ordinary
    action - deleting an account, a routine, a custom exercise - degrades from a
    lookup to a full scan as the child table grows.
    """
    with engine.connect() as conn:
        uncovered = conn.execute(UNINDEXED_FOREIGN_KEYS).all()

    assert not uncovered, "foreign keys with no leading-column index: " + ", ".join(
        f"{child}.{column} -> {parent}" for child, column, parent in uncovered
    )


@pytest.mark.parametrize(
    "index_name,table,why",
    [
        (
            "ix_workout_sessions_user_status_ended",
            "workout_sessions",
            "duel scores and the party workout board range over ended_at, which "
            "ix_workout_sessions_user_started cannot serve",
        ),
        (
            "ix_points_ledger_user_time",
            "points_ledger",
            "league standings sum a week of one user's ledger",
        ),
        (
            "ix_set_entries_user_exercise_time",
            "set_entries",
            "an exercise's whole history for a user is one range scan",
        ),
        (
            "ix_activity_user_time",
            "activity_events",
            "the feed pages backwards by created_at",
        ),
        (
            "ix_activity_party_time",
            "activity_events",
            "the party feed pages backwards by created_at",
        ),
    ],
)
def test_the_read_path_indexes_exist(engine: Engine, index_name: str, table: str, why: str):
    """Named individually, because each one is load-bearing for a specific query.

    A rename that loses one would otherwise only show up as a slow endpoint
    under load, months later.
    """
    with engine.connect() as conn:
        found = conn.execute(
            text("SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :i"),
            {"t": table, "i": index_name},
        ).scalar()
    assert found, f"{index_name} is missing from {table}: {why}"


def test_the_ledger_idempotency_guard_covers_every_once_only_award(engine: Engine):
    """uq_points_ledger_once must name every source that is paid exactly once.

    This is the test that was impossible before: the model listed three sources
    and the migration listed four, and because the suite builds its schema from
    the models, the 'duel_won' guard existed in production and was absent here.
    A duel is judged by whoever reads it first, so two simultaneous readers must
    not both pay the winner - this index is what makes that true underneath the
    level_progress row lock.

    'set_logged' and 'pr_achieved' are deliberately NOT covered: editing a set
    legitimately reverses and re-awards the same source id.
    """
    with engine.connect() as conn:
        predicate = conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_points_ledger_once'")
        ).scalar()

    assert predicate, "uq_points_ledger_once does not exist"
    for source in ("session_completed", "streak_bonus", "duel_won", "reversal"):
        assert source in predicate, f"{source} is paid once but is not guarded"
    for source in ("set_logged", "pr_achieved"):
        assert source not in predicate, (
            f"{source} is re-awarded on edit and must not be guarded"
        )
