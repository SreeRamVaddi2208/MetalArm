"""Training path payloads (app/api/routes/training_paths.py)."""

from pydantic import BaseModel, ConfigDict


class TrainingCategoryOut(BaseModel):
    """What a path is, and how it trains. The clients render the cards from
    this, so changing the copy or the numbers is a data change."""

    model_config = ConfigDict(from_attributes=True)

    category: str
    display_name: str
    tagline: str
    description: str
    rep_range_low: int
    rep_range_high: int
    relative_load: str
    relative_volume: str
    rest_seconds_guidance: int
    emphasis_tags: list[str]
