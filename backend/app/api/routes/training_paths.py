"""What each training path means.

One endpoint, so neither client hardcodes the copy or the numbers: the
onboarding cards, the profile setting and anything that suggests work all read
the same rows (app/core/training_categories.py).

The path itself is set with PATCH /auth/me {character_class} - the same field
the character sheet already used - because identity comes from the token and no
route in this API takes a user id.
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.core import training_categories
from app.schemas.training_category import TrainingCategoryOut

router = APIRouter(prefix="/training-categories", tags=["training"])


@router.get("", response_model=list[TrainingCategoryOut])
def list_training_categories(current_user: CurrentUser, db: DbSession) -> list[TrainingCategoryOut]:
    """The three paths, in the order they are offered."""
    return [
        TrainingCategoryOut.model_validate(profile)
        for profile in training_categories.all_profiles(db)
    ]
