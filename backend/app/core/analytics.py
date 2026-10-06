"""Analytics read models - pure functions from workout facts to the numbers
the clarity screens show. No database, no request: the routes load the facts
and these compute, so every figure can be checked by hand against a fixture.

Phase 1 needs only the muscle map of one session; snapshot deltas, series,
the calendar and recovery join it in phase 2.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

# A working set loads its exercise's primary muscles fully and the secondary
# ones half - the same weights the recovery model will use.
PRIMARY_WEIGHT = 1.0
SECONDARY_WEIGHT = 0.5


def muscle_load(sets: Iterable[tuple[Sequence[str], Sequence[str]]]) -> dict[str, float]:
    """Raw load per muscle group from working sets, each given as
    (primary muscle codes, secondary muscle codes)."""
    load: dict[str, float] = {}
    for primary, secondary in sets:
        for code in primary:
            load[code] = load.get(code, 0.0) + PRIMARY_WEIGHT
        for code in secondary:
            if code not in primary:
                load[code] = load.get(code, 0.0) + SECONDARY_WEIGHT
    return load


def muscle_intensity(sets: Iterable[tuple[Sequence[str], Sequence[str]]]) -> dict[str, float]:
    """0-1 per muscle group, relative to the most-worked one - what the body
    map fills with. Cardio and full-body are not places on a body."""
    load = {k: v for k, v in muscle_load(sets).items() if k not in ("cardio", "full_body")}
    top = max(load.values(), default=0.0)
    if top <= 0:
        return {}
    return {code: round(value / top, 3) for code, value in sorted(load.items())}
