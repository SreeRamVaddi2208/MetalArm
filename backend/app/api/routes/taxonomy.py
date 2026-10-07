"""The exercise taxonomy: muscle groups and equipment, for browse grids and
the body map. Public reference data, but behind auth like the rest of the
library."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.core import taxonomy
from app.schemas.taxonomy import EquipmentOut, MuscleGroupOut, TaxonomyOut

router = APIRouter(tags=["taxonomy"])


@router.get("/taxonomy", response_model=TaxonomyOut)
def read_taxonomy(current_user: CurrentUser, db: DbSession) -> TaxonomyOut:
    """Every muscle group and piece of equipment, in display order."""
    return TaxonomyOut(
        muscle_groups=[MuscleGroupOut.model_validate(m) for m in taxonomy.muscles(db)],
        equipment=[EquipmentOut.model_validate(e) for e in taxonomy.equipment(db)],
    )
