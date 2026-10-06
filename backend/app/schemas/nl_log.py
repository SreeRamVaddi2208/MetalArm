"""Natural-language set logging: request and response shapes."""

import uuid

from pydantic import BaseModel, Field

from app.core import workout_rules as rules
from app.models.workout_enums import WeightUnit


class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    # The live workout: "same again", the default exercise and carried weight
    # all come from it. Optional - a parse outside a workout still works.
    session_id: uuid.UUID | None = None
    # The exercise card the user is on, if the session has not logged it yet.
    exercise_id: uuid.UUID | None = None


class ProposedSetOut(BaseModel):
    exercise_id: uuid.UUID
    exercise_name: str
    # In `unit`, exactly as it should be sent to the log-set endpoint, which
    # converts pounds to kilograms itself.
    weight: float
    unit: str
    reps: int | None
    rpe: float | None
    is_warmup: bool


class AlternativeOut(BaseModel):
    exercise_id: uuid.UUID
    name: str
    confidence: float


class ParseResponse(BaseModel):
    parse_id: uuid.UUID
    # 'grammar' | 'llm' | 'none'
    parser_used: str
    # One entry per set to log: "3 sets of 8" is three entries. Nothing is
    # logged until the client sends each to POST /workouts/sessions/{id}/sets.
    proposed_sets: list[ProposedSetOut]
    set_count: int
    exercise_confidence: float
    # Up to three, when the exercise match is not confident.
    exercise_alternatives: list[AlternativeOut]
    # Words that were heard but not used, so the user sees what was ignored.
    unparsed_fragments: list[str]
    # Set when nothing could be proposed - a message to show as-is.
    problem: str | None = None


class CorrectedSet(BaseModel):
    exercise_id: uuid.UUID
    weight: float = Field(ge=0, le=rules.MAX_WEIGHT_KG / rules.LB_TO_KG)
    unit: WeightUnit = WeightUnit.KG
    reps: int | None = Field(default=None, ge=1, le=rules.MAX_REPS)
    rpe: float | None = Field(default=None, ge=1, le=10)
    is_warmup: bool = False
    set_count: int = Field(default=1, ge=1, le=20)


class ParseFeedback(BaseModel):
    # True: logged as proposed. False: edited first (send corrected_result),
    # or thrown away (send nothing else).
    accepted: bool
    corrected_result: CorrectedSet | None = None


class ParseFeedbackResponse(BaseModel):
    # A phrase corrected to the same exercise often enough becomes an alias.
    alias_learned: bool


class AliasCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=60)
    exercise_id: uuid.UUID


class AliasOut(BaseModel):
    id: uuid.UUID
    alias: str
    exercise_id: uuid.UUID
    exercise_name: str
    # 'seed' | 'user' | 'learned'
    source: str
