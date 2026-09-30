"""Index the unindexed foreign keys, and the ended_at range.

Postgres indexes the *referenced* side of a foreign key automatically and the
*referencing* side not at all. Five columns were left uncovered, and each one
turns an ordinary user action into a sequential scan of a child table:

    party_quests.created_by      SET NULL  - deleting an account scans every
                                            party quest ever created
    duels.winner_id              SET NULL  - deleting an account scans duels
                                            (ix_duels_challenger/_opponent do
                                            not cover this column)
    raid_hits.session_id         CASCADE   - deleting a workout session scans
                                            raid_hits; uq_raid_hits_boss_session
                                            is (boss_id, session_id), so
                                            session_id is the TRAILING column
                                            and cannot serve the check
    workout_sessions.routine_id  SET NULL  - deleting a routine scans sessions
    personal_records.exercise_id CASCADE   - deleting a custom exercise scans
                                            personal_records

Plus one read-path index. workout_sessions.ended_at is the most range-filtered
column in the application - every duel score (app/core/duels.py) and the party
workout leaderboard bound on it - and it had no index at all. It cannot be
swapped for the indexed started_at: a workout belongs to the window it was
FINISHED in, which duels.py documents, so a session cannot count for a duel that
closed while it was still running.

CONCURRENTLY, and therefore in an autocommit block. These tables are small today
but they are the ones projected to hold billions of rows, and a plain CREATE
INDEX takes ACCESS EXCLUSIVE for the whole build - a write outage. This is the
pattern every index migration from here on should follow.

One caveat that comes with CONCURRENTLY: a build that fails partway leaves an
INVALID index behind, which Postgres will not use and will not clean up. Recover
by dropping it by name and re-running:

    DROP INDEX CONCURRENTLY IF EXISTS <name>;

Nothing here touches uq_points_ledger_once. That index already covers
'duel_won' in every migrated database; what was wrong was the model's copy of
the predicate, which is a Python fix with no DDL.

Revision ID: b7e4a2c91d35
Revises: 8d1f4c60ba57
Create Date: 2026-09-30 11:05:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = 'b7e4a2c91d35'
down_revision: str | None = '8d1f4c60ba57'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (index name, table, columns)
INDEXES: tuple[tuple[str, str, list[str]], ...] = (
    ("ix_party_quests_created_by", "party_quests", ["created_by"]),
    ("ix_duels_winner_id", "duels", ["winner_id"]),
    ("ix_raid_hits_session_id", "raid_hits", ["session_id"]),
    ("ix_workout_sessions_routine_id", "workout_sessions", ["routine_id"]),
    ("ix_personal_records_exercise_id", "personal_records", ["exercise_id"]),
    (
        "ix_workout_sessions_user_status_ended",
        "workout_sessions",
        ["user_id", "status", "ended_at"],
    ),
)


def upgrade() -> None:
    # CONCURRENTLY cannot run inside a transaction, and env.py wraps every
    # migration in one, so step outside it.
    with op.get_context().autocommit_block():
        for name, table, columns in INDEXES:
            op.create_index(
                name,
                table,
                columns,
                unique=False,
                postgresql_concurrently=True,
                if_not_exists=True,
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, table, _ in reversed(INDEXES):
            op.drop_index(
                name,
                table_name=table,
                postgresql_concurrently=True,
                if_exists=True,
            )
