"""Taxonomy response shapes."""

from pydantic import BaseModel, ConfigDict


class MuscleGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    display_name: str
    # 'front' | 'back' | 'both' | 'none'
    body_side: str
    # Body-map SVG path ids this muscle fills.
    svg_path_ids: list[str]
    # 'small' | 'large' - how fast it recovers.
    size_class: str
    # Asset-registry key for the browse tile.
    tile_asset: str
    # Shown in the Explore grid; the rest still light the body map.
    browsable: bool


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    display_name: str
    icon_asset: str
    browsable: bool


class TaxonomyOut(BaseModel):
    muscle_groups: list[MuscleGroupOut]
    equipment: list[EquipmentOut]
