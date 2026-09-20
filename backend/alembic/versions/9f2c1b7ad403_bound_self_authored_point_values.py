"""bound self-authored point values

A quest's points_reward and a reward's point_cost had a floor but no ceiling,
while the columns are INTEGER: points_reward=3_000_000_000 overflowed and the
client got a 500 ("integer out of range") instead of a 422. The schemas now
reject it, and these constraints are the backstop - the same pairing
xp_reward already had (ck_quests_xp_reward_range).

Hand-written: Alembic's autogenerate does not diff CheckConstraints.

Revision ID: 9f2c1b7ad403
Revises: e6ab950c84ea
Create Date: 2026-09-20 02:20:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = '9f2c1b7ad403'
down_revision: str | None = 'e6ab950c84ea'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAX_POINTS_REWARD = 10_000
MAX_POINT_COST = 1_000_000


def upgrade() -> None:
    # Clamp anything already over the new ceiling, so the constraint can be
    # added without failing on existing rows.
    op.execute(
        f"UPDATE quests SET points_reward = {MAX_POINTS_REWARD} "
        f"WHERE points_reward > {MAX_POINTS_REWARD}"
    )
    op.execute(
        f"UPDATE party_quests SET points_reward = {MAX_POINTS_REWARD} "
        f"WHERE points_reward > {MAX_POINTS_REWARD}"
    )
    op.execute(
        f"UPDATE reward_items SET point_cost = {MAX_POINT_COST} "
        f"WHERE point_cost > {MAX_POINT_COST}"
    )

    op.drop_constraint('ck_quests_points_non_negative', 'quests', type_='check')
    op.create_check_constraint(
        'ck_quests_points_reward_range',
        'quests',
        f'points_reward >= 0 AND points_reward <= {MAX_POINTS_REWARD}',
    )

    op.drop_constraint('ck_party_quests_points_non_negative', 'party_quests', type_='check')
    op.create_check_constraint(
        'ck_party_quests_points_reward_range',
        'party_quests',
        f'points_reward >= 0 AND points_reward <= {MAX_POINTS_REWARD}',
    )

    op.drop_constraint('ck_reward_items_cost_positive', 'reward_items', type_='check')
    op.create_check_constraint(
        'ck_reward_items_cost_range',
        'reward_items',
        f'point_cost > 0 AND point_cost <= {MAX_POINT_COST}',
    )


def downgrade() -> None:
    op.drop_constraint('ck_reward_items_cost_range', 'reward_items', type_='check')
    op.create_check_constraint('ck_reward_items_cost_positive', 'reward_items', 'point_cost > 0')

    op.drop_constraint('ck_party_quests_points_reward_range', 'party_quests', type_='check')
    op.create_check_constraint(
        'ck_party_quests_points_non_negative', 'party_quests', 'points_reward >= 0'
    )

    op.drop_constraint('ck_quests_points_reward_range', 'quests', type_='check')
    op.create_check_constraint('ck_quests_points_non_negative', 'quests', 'points_reward >= 0')
