"""Tier 1 of natural-language set logging: a deterministic grammar.

"bench 80 for 8", "3 sets of 8 at 80", "same again", "eighty kilos for eight,
warm-up" - turned into proposed sets the user confirms with one tap. Pure: no
database, no network, no clock. app/core/nl_log.py loads the context (the
user's exercises and aliases, the live session's last set) and falls back to
the LLM (nl_llm.py) only when this cannot make sense of the text.

A parse PROPOSES; it never logs. Confirmed sets go through the ordinary
log-set endpoint, so nothing here can award a point or set a record.

The pipeline:
  1. normalize - lowercase, units and number words to a canonical form,
     common transcription slips repaired ("80 4 8" is "80 for 8").
  2. modifiers - warm-up and RPE are lifted out first, so "at 8" meaning RPE
     cannot be mistaken for a weight.
  3. the set pattern - the first of a fixed list of shapes that matches.
  4. the exercise - from what is left: alias or name, then fuzzy, else the
     exercise the session is on.
"""

from __future__ import annotations

import dataclasses
import difflib
import re
import uuid
from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.core import workout_rules as rules
from app.core.exercise_names import name_key

# Below this the exercise is still proposed, but with alternatives to pick from.
CONFIDENT = 0.85
# Below this a fuzzy match is not a match at all.
FUZZY_FLOOR = 0.6
MAX_SETS = 20


@dataclasses.dataclass(frozen=True)
class Candidate:
    id: uuid.UUID
    name: str
    is_bodyweight: bool = False


@dataclasses.dataclass(frozen=True)
class LastSet:
    exercise_id: uuid.UUID
    weight_kg: Decimal
    reps: int | None
    rpe: Decimal | None = None
    is_warmup: bool = False


@dataclasses.dataclass(frozen=True)
class ParseContext:
    candidates: Sequence[Candidate]
    # alias (name_key form) -> exercise id, personal aliases already applied.
    aliases: Mapping[str, uuid.UUID] = dataclasses.field(default_factory=dict)
    # The exercise the session is on: the default when none is named.
    current_exercise_id: uuid.UUID | None = None
    # The last set logged this session, for "same again" and carried weight.
    last_set: LastSet | None = None
    # The user's unit, for a weight said with none.
    unit: str = "kg"


@dataclasses.dataclass(frozen=True)
class ProposedSet:
    exercise_id: uuid.UUID | None
    weight: float
    unit: str
    reps: int | None
    rpe: float | None = None
    is_warmup: bool = False


@dataclasses.dataclass(frozen=True)
class Alternative:
    exercise_id: uuid.UUID
    name: str
    confidence: float


@dataclasses.dataclass(frozen=True)
class ParseResult:
    # One entry per set to log, already expanded: "3 sets of 8" is three.
    sets: tuple[ProposedSet, ...] = ()
    exercise_confidence: float = 0.0
    alternatives: tuple[Alternative, ...] = ()
    unparsed: tuple[str, ...] = ()
    # Why nothing was proposed, for the "couldn't understand that" message.
    problem: str = ""
    # The words taken to name the exercise ("flat bench"), so a correction
    # can teach that phrase as an alias.
    phrase: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.sets)


# ---------------------------------------------------------------------------
# 1. Normalization
# ---------------------------------------------------------------------------

_UNITS = {
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg", "kilograms": "kg",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
}
_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_NUMBER_WORDS = set(_ONES) | set(_TENS) | {"hundred", "thousand"}
# Phrases meaning "repeat the last set". Matched before number words, or the
# "one" in "another one" would become a rep count.
_REPEAT = re.compile(
    r"\b(?:same again|same as (?:before|last time)|another one|one more|again|repeat|ditto|same)\b"
)
_WARMUP = re.compile(r"\bwarm\s?ups?\b")
# Words that carry no meaning here, dropped before the exercise is matched.
_FILLER = {
    "i", "did", "do", "just", "then", "and", "of", "a", "an", "the", "at", "with", "on",
    "please", "log", "logged", "set", "sets", "rep", "reps", "for", "x", "um", "uh", "er",
    "like", "okay", "ok", "so", "my", "now", "got", "make", "that", "it", "was", "times",
    "by", "weight", "same", "to", "in", "is", "add", "next",
}


def _words_to_number(words: list[str]) -> float | None:
    """'eighty five' -> 85, 'one hundred and twenty' -> 120, 'two twenty
    five' -> 225 (how weights are said aloud), 'a hundred' -> 100."""
    if not words:
        return None
    # The gym idiom: a single digit then a tens word is hundreds.
    if len(words) >= 2 and words[0] in _ONES and _ONES[words[0]] < 10 and words[1] in _TENS:
        rest = _words_to_number(words[1:])
        return None if rest is None else _ONES[words[0]] * 100 + rest
    total = current = 0
    for word in words:
        if word in _ONES:
            current += _ONES[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred":
            current = (current or 1) * 100
        elif word == "thousand":
            total += (current or 1) * 1000
            current = 0
        elif word in ("and", "a"):
            continue
        else:
            return None
    return float(total + current)


def _fmt(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


def _number_words(text: str) -> str:
    """Replace runs of number words with digits. 'and a half' and 'point
    five' become decimals."""
    tokens = text.split()
    out: list[str] = []
    i = 0
    while i < len(tokens):
        if tokens[i] in _NUMBER_WORDS or (
            tokens[i] == "a" and i + 1 < len(tokens) and tokens[i + 1] == "hundred"
        ):
            j = i
            run: list[str] = []
            while j < len(tokens) and (
                tokens[j] in _NUMBER_WORDS
                or (tokens[j] in ("and", "a") and j + 1 < len(tokens) and tokens[j + 1] in _NUMBER_WORDS)
            ):
                run.append(tokens[j])
                j += 1
            value = _words_to_number(run)
            if value is None:
                out.append(tokens[i])
                i += 1
                continue
            # "point five" / "and a half"
            if j + 1 < len(tokens) and tokens[j] == "point" and tokens[j + 1] in _ONES:
                value += _ONES[tokens[j + 1]] / 10
                j += 2
            elif tokens[j : j + 3] == ["and", "a", "half"]:
                value += 0.5
                j += 3
            out.append(_fmt(value))
            i = j
            continue
        out.append(tokens[i])
        i += 1
    return " ".join(out)


def normalize(text: str) -> str:
    """A canonical lowercase form the patterns below can rely on."""
    t = text.casefold()
    t = t.replace("×", " x ").replace("@", " at ")
    # "80kg" -> "80 kg", "3x8" -> "3 x 8"
    t = re.sub(r"(\d)\s*(kgs?|kilos?|kilograms?|lbs?|pounds?)\b", r"\1 \2", t)
    t = re.sub(r"(\d)\s*x\s*(\d)", r"\1 x \2", t)
    t = re.sub(r"(?<![\w.])(\d+),(\d)(?!\d)", r"\1.\2", t)  # "82,5" -> "82.5"
    t = re.sub(r"[^\w\s.\-]", " ", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)  # sentence dots, not decimals
    t = t.replace("-", " ")
    t = " ".join(_UNITS.get(w, w) for w in t.split())
    t = _number_words(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ---------------------------------------------------------------------------
# 2-3. Modifiers and the set pattern
# ---------------------------------------------------------------------------

W = r"(?P<weight>\d+(?:\.\d+)?)"
UNIT = r"(?:\s*(?P<unit>kg|lb))?"
REPS = r"(?P<reps>\d+)"
NOT_UNIT = r"(?!\s*(?:kg|lb))"
# Ordered: the first shape that matches wins.
_PATTERNS: list[re.Pattern[str]] = [
    # 3 sets of 8 at 80 / 3 x 8 at 80 kg / 3 sets of 8 reps with 80
    re.compile(
        rf"\b(?P<sets>\d+)\s*(?:sets?(?:\s*of)?|x)\s*{REPS}(?:\s*reps?)?\s*(?:at|with|of)\s*{W}{UNIT}"
    ),
    # 80 kg for 8 / 80 x 8 / 80 for 8 reps - optionally "for 3 sets" after
    re.compile(
        rf"\b{W}{UNIT}\s*(?:for|x|by)\s*{REPS}(?:\s*reps?)?"
        rf"(?:\s*(?:x|for|times)?\s*(?P<sets>\d+)\s*sets?)?\b"
    ),
    # 80 kg 8 reps
    re.compile(rf"\b{W}\s*(?P<unit>kg|lb)\s*{REPS}\s*reps?\b"),
    # 8 reps at 80 / 8 reps with 80 kg
    re.compile(rf"\b{REPS}\s*reps?\s*(?:at|with)\s*{W}{UNIT}"),
    # "for" heard as "4": 80 4 8
    re.compile(rf"\b{W}{UNIT}\s+4\s+{REPS}\b{NOT_UNIT}"),
    # 8 reps - the weight carries over - or 3 sets of 8 reps
    re.compile(rf"\b(?:(?P<sets>\d+)\s*sets?\s*(?:of\s*)?)?{REPS}\s*reps?\b"),
    # "same weight for 6" / "for 6": reps only, the weight carries over
    re.compile(rf"(?:^|\s)(?:for|x)\s*{REPS}\b{NOT_UNIT}(?!\s*sets?)"),
    # 80 8 - two bare numbers: weight, then reps
    re.compile(rf"\b{W}{UNIT}\s+{REPS}\b{NOT_UNIT}"),
]
_RPE = re.compile(r"\brpe\s*(?:of\s*)?(?:at\s*)?(\d+(?:\.\d+)?)")
_RPE_AT = re.compile(r"\bat\s*(\d+(?:\.\d+)?)\s*$")
_TRAILING_SETS = re.compile(r"\b(?:x\s*|for\s*)?(\d+)\s*sets?\b")


@dataclasses.dataclass
class _Shape:
    sets: int = 1
    reps: int | None = None
    weight: float | None = None
    unit: str | None = None
    rpe: float | None = None
    warmup: bool = False
    repeat: bool = False


def _cut(text: str, match: re.Match[str]) -> str:
    return (text[: match.start()] + " " + text[match.end() :]).strip()


def _shape(text: str) -> tuple[_Shape, str]:
    """The set's numbers, and the text that is left for the exercise."""
    shape = _Shape()
    # Before number words: the "one" in "another one" is not a rep count.
    if m := _REPEAT.search(text):
        shape.repeat = True
        text = _cut(text, m)
    text = normalize(text)
    if m := _WARMUP.search(text):
        shape.warmup = True
        text = _cut(text, m)
    if m := _RPE.search(text):
        shape.rpe = float(m.group(1))
        text = _cut(text, m)

    for pattern in _PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        groups = m.groupdict()
        shape.reps = int(float(groups["reps"]))
        if groups.get("weight") is not None:
            shape.weight = float(groups["weight"])
        shape.unit = groups.get("unit")
        if groups.get("sets"):
            shape.sets = int(groups["sets"])
        text = _cut(text, m)
        break

    if shape.reps is not None and shape.sets == 1 and (m := _TRAILING_SETS.search(text)):
        shape.sets = int(m.group(1))
        text = _cut(text, m)
    # "80 for 8 at 8": a bare "at N" left over after a full set is an RPE.
    if shape.rpe is None and shape.weight is not None and (m := _RPE_AT.search(text)):
        value = float(m.group(1))
        if 1 <= value <= 10:
            shape.rpe = value
            text = _cut(text, m)
    return shape, text


# ---------------------------------------------------------------------------
# 4. The exercise
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class _ExerciseMatch:
    exercise_id: uuid.UUID | None
    confidence: float
    alternatives: tuple[Alternative, ...]
    leftover: tuple[str, ...]
    phrase: str = ""


def _vocabulary(ctx: ParseContext) -> dict[str, uuid.UUID]:
    """Every phrase that names an exercise: names first, aliases over them
    (a user's "press" should mean what they said it means)."""
    vocab = {name_key(c.name): c.id for c in ctx.candidates}
    visible = {c.id for c in ctx.candidates}
    vocab.update({alias: eid for alias, eid in ctx.aliases.items() if eid in visible})
    return vocab


def _resolve(text: str, ctx: ParseContext) -> _ExerciseMatch:
    words = [w for w in text.split() if w not in _FILLER and not re.fullmatch(r"[\d.]+", w)]
    if not words:
        return _ExerciseMatch(ctx.current_exercise_id, 1.0 if ctx.current_exercise_id else 0.0, (), ())
    vocab = _vocabulary(ctx)
    names = {c.id: c.name for c in ctx.candidates}

    # Longest run of words that is a known phrase, exactly.
    for size in range(len(words), 0, -1):
        for start in range(0, len(words) - size + 1):
            phrase = " ".join(words[start : start + size])
            if phrase in vocab:
                leftover = tuple(words[:start] + words[start + size :])
                return _ExerciseMatch(vocab[phrase], 1.0, (), leftover, phrase)

    # Fuzzy, on the whole remaining phrase.
    phrase = " ".join(words)
    scored: dict[uuid.UUID, float] = {}
    for known, eid in vocab.items():
        score = difflib.SequenceMatcher(None, phrase, known).ratio()
        scored[eid] = max(scored.get(eid, 0.0), score)
    ranked = sorted(scored.items(), key=lambda kv: (-kv[1], names.get(kv[0], "")))
    best = [(eid, s) for eid, s in ranked if s >= FUZZY_FLOOR][:3]
    if not best:
        # Unrecognised words: keep the session's exercise, but say what was
        # ignored rather than pretending it was understood.
        return _ExerciseMatch(
            ctx.current_exercise_id, 1.0 if ctx.current_exercise_id else 0.0, (), tuple(words),
            phrase,
        )
    top_id, top = best[0]
    alternatives = (
        tuple(Alternative(eid, names[eid], round(s, 2)) for eid, s in best)
        if top < CONFIDENT
        else ()
    )
    return _ExerciseMatch(top_id, round(top, 2), alternatives, (), phrase)


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------


def _kg_to(unit: str, kg: Decimal) -> float:
    value = float(kg) if unit == "kg" else float(kg) / rules.LB_TO_KG
    return round(value, 1)


def in_bounds(weight: float, unit: str, reps: int | None, rpe: float | None, sets: int) -> str:
    kg = weight * (rules.LB_TO_KG if unit == "lb" else 1)
    if not 0 <= kg <= rules.MAX_WEIGHT_KG:
        return f"That weight is over {rules.MAX_WEIGHT_KG} kg"
    if reps is not None and not 1 <= reps <= rules.MAX_REPS:
        return "That rep count doesn't look right"
    if rpe is not None and not 1 <= rpe <= 10:
        return "RPE runs from 1 to 10"
    if not 1 <= sets <= MAX_SETS:
        return f"At most {MAX_SETS} sets at a time"
    return ""


def parse(text: str, ctx: ParseContext) -> ParseResult:
    """Proposed sets for `text`, or a result with `problem` set."""
    raw = text.strip()
    if not raw:
        return ParseResult(problem="Nothing was said")

    shape, rest = _shape(raw.casefold())
    exercise = _resolve(rest, ctx)
    last = ctx.last_set

    if shape.repeat and shape.reps is None:
        if last is None:
            return ParseResult(problem="There's no set to repeat yet")
        unit = ctx.unit
        proposed = ProposedSet(
            exercise_id=last.exercise_id,
            weight=_kg_to(unit, last.weight_kg),
            unit=unit,
            reps=last.reps,
            rpe=shape.rpe if shape.rpe is not None else (float(last.rpe) if last.rpe else None),
            is_warmup=shape.warmup or last.is_warmup,
        )
        return ParseResult(
            sets=(proposed,) * shape.sets,
            exercise_confidence=1.0,
            unparsed=exercise.leftover,
        )

    if shape.reps is None:
        return ParseResult(
            problem="Couldn't find a set in that - try \"80 for 8\"",
            unparsed=tuple(rest.split()),
        )

    exercise_id = exercise.exercise_id
    if shape.weight is not None:
        weight, unit = shape.weight, shape.unit or ctx.unit
    elif last is not None and (exercise_id is None or last.exercise_id == exercise_id):
        # "8 reps": the weight carries over from the last set.
        weight, unit = _kg_to(ctx.unit, last.weight_kg), ctx.unit
        exercise_id = exercise_id or last.exercise_id
    else:
        candidate = next((c for c in ctx.candidates if c.id == exercise_id), None)
        if candidate is None or not candidate.is_bodyweight:
            return ParseResult(
                problem="What weight was that?", unparsed=exercise.leftover,
                exercise_confidence=exercise.confidence, alternatives=exercise.alternatives,
            )
        weight, unit = 0.0, ctx.unit

    if exercise_id is None:
        return ParseResult(
            problem="Which exercise was that?", unparsed=exercise.leftover,
            phrase=exercise.phrase,
        )

    problem = in_bounds(weight, unit, shape.reps, shape.rpe, shape.sets)
    if problem:
        return ParseResult(problem=problem)

    proposed = ProposedSet(
        exercise_id=exercise_id,
        weight=weight,
        unit=unit,
        reps=shape.reps,
        rpe=shape.rpe,
        is_warmup=shape.warmup,
    )
    return ParseResult(
        sets=(proposed,) * shape.sets,
        exercise_confidence=exercise.confidence,
        alternatives=exercise.alternatives,
        unparsed=exercise.leftover,
        phrase=exercise.phrase,
    )
