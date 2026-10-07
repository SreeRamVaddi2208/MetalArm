"""Tier 2 of natural-language set logging: Claude, when the grammar fails.

Only reached when nl_parser.parse() proposes nothing. The model sees the text,
the user's candidate exercises (id + name) and the session's current exercise,
and must answer in a strict JSON schema with the same fields tier 1 fills -
nothing else. Its answer is then checked like untrusted input, because it is:

- an exercise id not in the candidate list is rejected, so the model cannot
  invent an exercise or reach one the user cannot see;
- every number goes through nl_parser's own bounds;
- it never sees, and cannot produce, a point value - a confirmed set is
  scored by the log-set endpoint like any other.

Every failure - no key configured, timeout, refusal, bad JSON, a rejected
answer - comes back as "couldn't parse", never as an error. The user then just
types it.
"""

from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal

from app.core import nl_parser as tier1
from app.core.config import get_settings

logger = logging.getLogger("metalarm.nl_llm")

_SYSTEM = (
    "You turn one spoken or typed gym set log into structured data. The user is "
    "mid-workout; the text may be a speech-to-text transcript with slips. "
    "Choose exercise_id only from the candidate list given, or null when none "
    "fits or the text names no exercise. weight is in the unit stated, else the "
    "user's default unit; null when not said. reps and sets are whole numbers; "
    "sets is how many identical sets were described (1 if not said). rpe is 1-10 "
    "or null. is_warmup is true only if the text says warm-up. If the text is not "
    "a set log at all, return understood false."
)

def _nullable(kind: str) -> dict:
    # anyOf rather than a type array: anyOf is what structured outputs
    # documents as supported.
    return {"anyOf": [{"type": kind}, {"type": "null"}]}


_SCHEMA = {
    "type": "object",
    "properties": {
        "understood": {"type": "boolean"},
        "exercise_id": _nullable("string"),
        "weight": _nullable("number"),
        "unit": {"type": "string", "enum": ["kg", "lb"]},
        "reps": _nullable("integer"),
        "sets": {"type": "integer"},
        "rpe": _nullable("number"),
        "is_warmup": {"type": "boolean"},
    },
    "required": ["understood", "exercise_id", "weight", "unit", "reps", "sets", "rpe", "is_warmup"],
    "additionalProperties": False,
}


def enabled() -> bool:
    return bool(get_settings().anthropic_api_key)


def _prompt(text: str, ctx: tier1.ParseContext) -> str:
    current = next((c.name for c in ctx.candidates if c.id == ctx.current_exercise_id), None)
    last = ctx.last_set
    lines = [
        f"Default unit: {ctx.unit}",
        f"Current exercise: {current or 'none'}",
        "Last set: "
        + (f"{last.weight_kg} kg x {last.reps}" if last is not None else "none"),
        "Candidates (id: name):",
        *(f"{c.id}: {c.name}" for c in ctx.candidates),
        "",
        f"Text: {text}",
    ]
    return "\n".join(lines)


_client = None


def _get_client():
    """One client for the process: its connection pool is reused, so a parse
    does not pay a TLS handshake inside its latency budget."""
    global _client
    if _client is None:
        import anthropic  # imported lazily: the app runs without the fallback

        settings = get_settings()
        _client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.nl_parse_timeout_s,
            # A retry would blow the latency budget; the user can say it again.
            max_retries=0,
        )
    return _client


def _call(text: str, ctx: tier1.ParseContext) -> dict | None:
    """The raw model answer, or None. Isolated so tests replace exactly this."""
    import anthropic

    settings = get_settings()
    client = _get_client()
    try:
        response = client.beta.messages.create(
            model=settings.nl_parse_model,
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _prompt(text, ctx)}],
            # A short extraction: lowest effort keeps it inside the budget.
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": _SCHEMA},
            },
            # A classifier decline is retried on Anthropic's recommended model
            # server-side rather than surfacing as a failed parse.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APITimeoutError:
        logger.info("nl parse: model timed out")
        return None
    except anthropic.RateLimitError:
        logger.warning("nl parse: rate limited")
        return None
    except anthropic.APIStatusError as exc:
        logger.warning("nl parse: API error %s", exc.status_code)
        return None
    except anthropic.APIConnectionError:
        logger.warning("nl parse: could not reach the API")
        return None

    if response.stop_reason == "refusal":
        return None
    block = next((b for b in response.content if b.type == "text"), None)
    if block is None:
        return None
    try:
        return json.loads(block.text)
    except ValueError:
        return None


def parse(text: str, ctx: tier1.ParseContext) -> tier1.ParseResult:
    """Tier 2. Always returns a ParseResult; `problem` set on any failure."""
    failed = tier1.ParseResult(problem="Couldn't understand that - try \"80 for 8\"")
    if not enabled():
        return failed
    answer = _call(text, ctx)
    if not answer or not answer.get("understood"):
        return failed

    allowed = {str(c.id): c for c in ctx.candidates}
    raw_id = answer.get("exercise_id")
    if raw_id is not None and raw_id not in allowed:
        # Not one of the user's exercises: never trust it.
        logger.warning("nl parse: model chose an exercise outside the candidates")
        return failed
    exercise_id = uuid.UUID(raw_id) if raw_id else ctx.current_exercise_id
    if exercise_id is None:
        return tier1.ParseResult(problem="Which exercise was that?")

    unit = answer.get("unit") if answer.get("unit") in ("kg", "lb") else ctx.unit
    reps, weight = answer.get("reps"), answer.get("weight")
    if not isinstance(reps, int) or isinstance(reps, bool):
        return failed
    if weight is None:
        last = ctx.last_set
        if last is not None and last.exercise_id == exercise_id:
            weight, unit = float(Decimal(last.weight_kg)), "kg"
        elif allowed.get(str(exercise_id)) and allowed[str(exercise_id)].is_bodyweight:
            weight = 0.0
        else:
            return tier1.ParseResult(problem="What weight was that?")
    sets = answer.get("sets") if isinstance(answer.get("sets"), int) else 1
    rpe = answer.get("rpe")
    problem = tier1.in_bounds(float(weight), unit, reps, rpe, sets)
    if problem:
        return tier1.ParseResult(problem=problem)

    proposed = tier1.ProposedSet(
        exercise_id=exercise_id,
        weight=float(weight),
        unit=unit,
        reps=reps,
        rpe=float(rpe) if rpe is not None else None,
        is_warmup=bool(answer.get("is_warmup")),
    )
    # The model is not given a confidence to report; below tier 1's exact
    # matches, so the UI keeps the exercise visibly editable.
    return tier1.ParseResult(sets=(proposed,) * sets, exercise_confidence=0.8)
