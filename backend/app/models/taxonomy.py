"""The exercise taxonomy as data: muscle groups and equipment, with the names
and artwork the browse screens show.

The CODES are the existing vocabularies in workout_enums.py (MuscleGroup,
Equipment), which exercises.primary_muscle_groups and exercises.equipment
already store and CHECK. These tables add what a code alone cannot carry - a
display name, which side of the body map it lights, which artwork to draw -
so the browse grids and the body map come from the database rather than from
labels hardcoded in two clients. Seeded from app/data/taxonomy.json.
"""

import enum

from sqlalchemy import CheckConstraint, Integer, String, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import Timestamps
from app.models.workout_enums import Equipment, MuscleGroup, check_in


class BodySide(str, enum.Enum):
    FRONT = "front"
    BACK = "back"
    BOTH = "both"
    # Not on the body map at all (cardio, full body).
    NONE = "none"


class SizeClass(str, enum.Enum):
    """How fast a muscle recovers, for the recovery model (Phase 2)."""

    SMALL = "small"
    LARGE = "large"


class MuscleGroupInfo(Timestamps, Base):
    __tablename__ = "muscle_groups"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    body_side: Mapped[str] = mapped_column(String(8), nullable=False)
    # Which paths of the body-map SVGs this muscle fills
    # (frontend/metalarm/ui/body_map.py), e.g. ["front-chest-l", "front-chest-r"].
    svg_path_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, server_default=text("'{}'")
    )
    size_class: Mapped[str] = mapped_column(String(8), nullable=False)
    # The asset-registry key for its browse tile, e.g. "muscle/chest".
    tile_asset: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    # Hidden from the browse grid (full_body, and anything not worth a tile).
    browsable: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    __table_args__ = (
        CheckConstraint(check_in("code", MuscleGroup), name="ck_muscle_groups_code"),
        CheckConstraint(check_in("body_side", BodySide), name="ck_muscle_groups_side"),
        CheckConstraint(check_in("size_class", SizeClass), name="ck_muscle_groups_size"),
    )


class EquipmentInfo(Timestamps, Base):
    __tablename__ = "equipment"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    # Asset-registry key for its browse circle, e.g. "equipment/barbell".
    icon_asset: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    browsable: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    __table_args__ = (
        CheckConstraint(check_in("code", Equipment), name="ck_equipment_code"),
    )
