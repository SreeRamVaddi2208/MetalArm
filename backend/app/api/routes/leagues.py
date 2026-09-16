"""Weekly leagues: promotion and relegation over the points ledger."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.core import leagues, leveling
from app.core.periods import local_now
from app.schemas.league import LeagueEntryOut, LeagueOut

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("/current", response_model=LeagueOut)
def current_league(current_user: CurrentUser, db: DbSession) -> LeagueOut:
    """This week's league. The placement is created on first access, which is
    also when last week's result is judged (app/core/leagues.py) - so leagues
    need no scheduled job. Standings are the points ledger summed over the ISO
    week in UTC, never a stored score."""
    league = leagues.current(db, current_user)

    entries = []
    for standing in league.standings:
        today = local_now(standing.user.timezone).date()
        streak = leveling.effective_streak(
            standing.progress.current_streak, standing.progress.last_completed_on, today
        )
        entries.append(
            LeagueEntryOut(
                position=standing.position,
                user_id=standing.user.id,
                display_name=standing.user.display_name,
                points=standing.points,
                level=standing.progress.current_level,
                rank=leveling.rank_for(
                    standing.progress.current_level, streak, standing.progress.trials_passed
                ).value,
                is_me=standing.is_me,
            )
        )
    db.commit()  # persist the placement created above
    return LeagueOut(
        week_key=league.week_key,
        division=league.division,
        division_label=league.division_label,
        group_no=league.group_no,
        ends_at=league.ends_at,
        promoted_from=league.promoted_from,
        promote_cutoff=league.promote_cutoff,
        demote_cutoff=league.demote_cutoff,
        entries=entries,
    )
