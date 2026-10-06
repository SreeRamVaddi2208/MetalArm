"""Reading the generated-quest templates, and seeding them.

Config that ships with the image (app/data/quest_templates.json), seeded on
deploy and read from the database afterwards - the same arrangement as the
training paths, and for the same reason: a quest is tuning, and retuning one
should not need a release.

A template that leaves the file is DEACTIVATED, never deleted: assignments
point at it, and a user halfway through a quest keeps it. It simply stops
being handed out.
"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import quest_engine
from app.core import workout_rules as rules
from app.models.quest_board import QuestObjective, QuestPeriod, QuestTemplate

TEMPLATE_FILE = Path(__file__).resolve().parents[1] / "data" / "quest_templates.json"

_DEFAULT_REWARD = {
    QuestPeriod.DAILY.value: rules.DAILY_QUEST_POINTS,
    QuestPeriod.WEEKLY.value: rules.WEEKLY_QUEST_POINTS,
}
_FIELDS = (
    "title",
    "description",
    "period",
    "objective_type",
    "objective_params",
    "target_value",
    "reward_points",
    "eligible_categories",
    "is_active",
)


def definitions() -> list[dict]:
    """The shipped templates, validated. Raises ValueError naming every bad
    row, so a typo fails the deploy instead of shipping an unfinishable quest."""
    records = json.loads(TEMPLATE_FILE.read_text())
    errors: list[str] = []
    seen: set[str] = set()
    out: list[dict] = []
    for record in records:
        code = record.get("code", "?")
        try:
            if code in seen:
                raise ValueError("duplicate code")
            seen.add(code)
            period = QuestPeriod(record["period"]).value
            objective = QuestObjective(record["objective_type"])
            params = record.get("objective_params") or {}
            quest_engine.validate_params(objective, params)
            if int(record["target_value"]) < 1:
                raise ValueError("target_value must be at least 1")
            out.append(
                {
                    "code": code,
                    "title": record["title"],
                    "description": record["description"],
                    "period": period,
                    "objective_type": objective.value,
                    "objective_params": params,
                    "target_value": int(record["target_value"]),
                    "reward_points": int(record.get("reward_points") or _DEFAULT_REWARD[period]),
                    "eligible_categories": list(record.get("eligible_categories") or []),
                    "is_active": bool(record.get("is_active", True)),
                }
            )
        except (KeyError, ValueError) as exc:
            errors.append(f"  {code}: {exc}")
    if errors:
        raise ValueError("quest templates rejected:\n" + "\n".join(errors))
    return out


def seed(db: Session) -> int:
    """Upsert the shipped templates and deactivate any that left the file.
    Returns how many rows were written. Idempotent: run it on every deploy."""
    existing = {row.code: row for row in db.scalars(select(QuestTemplate))}
    shipped = definitions()
    written = 0
    for record in shipped:
        row = existing.get(record["code"])
        if row is None:
            db.add(QuestTemplate(**record))
            written += 1
            continue
        if any(getattr(row, field) != record[field] for field in _FIELDS):
            for field in _FIELDS:
                setattr(row, field, record[field])
            written += 1
    codes = {record["code"] for record in shipped}
    for code, row in existing.items():
        if code not in codes and row.is_active:
            row.is_active = False
            written += 1
    db.flush()
    return written
