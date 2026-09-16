"""The profile page: Stat Panel, lifetime stats, and badges.

Separate from GET /auth/me on purpose. `me` is called on every page load and
must stay cheap; this endpoint runs several aggregates and is only fetched when
the profile is actually opened.
"""

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core import badges as badge_rules
from app.core import character as character_sheet
from app.core import leveling, rank_trials
from app.core import workout_streaks
from app.core.periods import local_now
from app.core.workout_store import qualified_weeks, workout_points_credited
from app.models.workout import SetEntry, WorkoutSession
from app.models.workout_enums import SessionStatus
from app.models.party import (
    PartyMembership,
    PartyQuest,
    PartyQuestCompletion,
)
from app.models.quest import QuestCompletion
from app.models.reward import RewardRedemption
from app.schemas.profile import (
    BadgeOut,
    CharacterOut,
    LifetimeStats,
    ProfileOut,
    StatOut,
    TrialOut,
)
from app.schemas.user import ProgressOut, UserOut

router = APIRouter(prefix="/profile", tags=["profile"])


def _scalar(db: Session, stmt) -> int:
    return int(db.execute(stmt).scalar_one() or 0)


@router.get("", response_model=ProfileOut)
def read_profile(current_user: CurrentUser, db: DbSession) -> ProfileOut:
    progress = current_user.progress
    today = local_now(current_user.timezone).date()

    personal_completions = _scalar(
        db,
        select(func.count(QuestCompletion.id)).where(
            QuestCompletion.user_id == current_user.id
        ),
    )
    party_completions = _scalar(
        db,
        select(func.count(PartyQuestCompletion.id)).where(
            PartyQuestCompletion.user_id == current_user.id
        ),
    )
    redemptions = _scalar(
        db,
        select(func.count(RewardRedemption.id)).where(
            RewardRedemption.user_id == current_user.id
        ),
    )
    # Quests plus finished workouts - the same total the wallet reports.
    points_earned = _scalar(
        db,
        select(func.coalesce(func.sum(QuestCompletion.points_awarded), 0)).where(
            QuestCompletion.user_id == current_user.id
        ),
    ) + workout_points_credited(db, current_user.id)
    points_spent = _scalar(
        db,
        select(func.coalesce(func.sum(RewardRedemption.points_spent), 0)).where(
            RewardRedemption.user_id == current_user.id
        ),
    )
    parties_joined = _scalar(
        db,
        select(func.count()).select_from(PartyMembership).where(
            PartyMembership.user_id == current_user.id
        ),
    )
    party_xp = _scalar(
        db,
        select(func.coalesce(func.sum(PartyQuestCompletion.xp_awarded), 0))
        .join(PartyQuest, PartyQuest.id == PartyQuestCompletion.party_quest_id)
        .where(PartyQuestCompletion.user_id == current_user.id),
    )

    # --- Gym workout module ---
    workouts_completed = _scalar(
        db,
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.status == SessionStatus.COMPLETED.value,
        ),
    )
    # is_pr excludes first-ever baselines and is cleared on abandoned sets,
    # so this counts only genuine records.
    workout_prs = _scalar(
        db,
        select(func.count(SetEntry.id)).where(
            SetEntry.user_id == current_user.id, SetEntry.is_pr.is_(True)
        ),
    )
    total_volume = db.execute(
        select(func.coalesce(func.sum(SetEntry.weight_kg * SetEntry.reps), 0))
        .join(WorkoutSession, WorkoutSession.id == SetEntry.session_id)
        .where(
            SetEntry.user_id == current_user.id,
            WorkoutSession.status == SessionStatus.COMPLETED.value,
            SetEntry.is_warmup.is_(False),
            SetEntry.reps.is_not(None),
        )
    ).scalar_one()
    longest_workout_streak = workout_streaks.longest_weekly_streak(
        qualified_weeks(db, current_user.id)
    )

    computed = badge_rules.evaluate(
        badge_rules.BadgeInputs(
            # Party quests are quests too - excluding them would make the
            # counters disagree with what the user actually did.
            quests_completed=personal_completions + party_completions,
            longest_streak=progress.longest_streak,
            current_level=progress.current_level,
            rewards_redeemed=redemptions,
            parties_joined=parties_joined,
            party_xp=party_xp,
            total_xp=progress.total_xp,
            workouts_completed=workouts_completed,
            workout_prs=workout_prs,
            longest_workout_streak=longest_workout_streak,
        )
    )

    streak = leveling.effective_streak(
        progress.current_streak, progress.last_completed_on, today
    )
    rank = leveling.rank_for(progress.current_level, streak, progress.trials_passed)
    earned_by_level = leveling.rank_by_level(progress.current_level)
    next_up = leveling.next_rank_requirement(
        progress.current_level, streak, progress.trials_passed
    )
    trial = rank_trials.next_trial(progress.current_level, streak, progress.trials_passed)
    into, needed = leveling.progress_into_level(progress.total_xp)

    return ProfileOut(
        user=UserOut(
            id=current_user.id,
            email=current_user.email,
            display_name=current_user.display_name,
            timezone=current_user.timezone,
            created_at=current_user.created_at,
            weight_unit=current_user.weight_unit,
        ),
        progress=ProgressOut(
            total_xp=progress.total_xp,
            current_level=progress.current_level,
            points_balance=progress.points_balance,
            longest_streak=progress.longest_streak,
            last_completed_on=progress.last_completed_on,
            xp_into_level=into,
            xp_for_next_level=needed,
            current_streak=streak,
            streak_is_active=leveling.streak_is_active(
                progress.last_completed_on, today
            ),
            rank=rank.value,
            rank_by_level=earned_by_level.value,
            next_rank=next_up[0].value if next_up else None,
            next_rank_level=next_up[1] if next_up else None,
            next_rank_streak=next_up[2] if next_up else None,
            next_rank_trial=trial.description if trial else None,
            trials_passed=progress.trials_passed,
        ),
        stats=LifetimeStats(
            quests_completed=personal_completions,
            party_quests_completed=party_completions,
            rewards_redeemed=redemptions,
            points_earned=points_earned,
            points_spent=points_spent,
            parties_joined=parties_joined,
            party_xp_contributed=party_xp,
            member_since=current_user.created_at,
            workouts_completed=workouts_completed,
            workout_prs=workout_prs,
            total_volume_kg=round(float(total_volume), 2),
            longest_workout_streak=longest_workout_streak,
        ),
        badges=[
            BadgeOut(
                id=b.id,
                name=b.name,
                description=b.description,
                icon=b.icon,
                earned=b.earned,
                progress=b.progress,
                target=b.target,
                percent=b.percent,
            )
            for b in computed
        ],
        badges_earned=badge_rules.earned_count(computed),
        badges_total=len(computed),
    )


@router.get("/trials", response_model=list[TrialOut])
def rank_trial_status(current_user: CurrentUser, db: DbSession) -> list[TrialOut]:
    """The strength trials that gate ranks B, A and S: each lift's target at
    the user's latest bodyweight, their best so far, and whether it is passed
    (app/core/rank_trials.py). Targets are null until a bodyweight is logged."""
    return [TrialOut(**vars(status)) for status in rank_trials.statuses(db, current_user.id)]


@router.get("/character", response_model=CharacterOut)
def character(current_user: CurrentUser, db: DbSession) -> CharacterOut:
    """The character sheet: Strength, Endurance and Discipline, each 0-100 with
    the number behind it (app/core/character.py). The class only marks which
    stats are highlighted - it never changes a score."""
    sheet = character_sheet.sheet(db, current_user)
    return CharacterOut(
        character_class=sheet.character_class,
        class_label=sheet.class_label,
        stats=[StatOut(**vars(stat)) for stat in sheet.stats],
    )
