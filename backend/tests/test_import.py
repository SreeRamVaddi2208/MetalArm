"""Imports from Strong and Hevy (app/core/importer.py): both CSV formats,
exercise matching that respects equipment, custom exercises for the rest,
records rebuilt in date order, a file imported once, known workouts skipped,
and XP without points or streaks."""

import datetime as dt
import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import importer
from app.models.workout import PersonalRecord, WorkoutImport, WorkoutSession
from app.models.workout_enums import RecordType

IMPORT = "/api/v1/workouts/import"
NOW = dt.datetime(2026, 9, 14, 12, 0, tzinfo=dt.timezone.utc)

STRONG_HEADER = (
    "Date,Workout Name,Duration,Exercise Name,Set Order,Weight,Reps,Distance,Seconds,Notes,Workout Notes,RPE\n"
)
STRONG_ROWS = (
    "2026-09-01 18:00:00,Push Day,1h 5m,Bench Press (Barbell),W,40,10,0,0,,,\n"
    "2026-09-01 18:00:00,Push Day,1h 5m,Bench Press (Barbell),1,80,5,0,0,,,8\n"
    "2026-09-01 18:00:00,Push Day,1h 5m,Bench Press (Barbell),2,82.5,5,0,0,,,\n"
    "2026-09-01 18:00:00,Push Day,1h 5m,Rest Timer,,,,,90,,,\n"
    "2026-09-01 18:00:00,Push Day,1h 5m,Cable Kickback (Cable),1,15,12,0,0,,,\n"
    "2026-09-03 18:00:00,Legs,50m,Squat (Barbell),1,100,5,0,0,,,\n"
    "2026-09-03 18:00:00,Legs,50m,Squat (Smith Machine),1,90,8,0,0,,,\n"
    "2026-09-03 18:00:00,Legs,50m,Plank,1,0,0,0,60,,,\n"
    "2026-09-03 18:00:00,Legs,50m,Squat (Barbell),2,0,0,0,0,,,\n"
)
STRONG_CSV = STRONG_HEADER + STRONG_ROWS
STRONG_NEWER = STRONG_CSV + "2026-09-08 18:00:00,Push Day,1h,Bench Press (Barbell),1,85,3,0,0,,,\n"

HEVY_CSV = (
    '"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes",'
    '"set_index","set_type","weight_lbs","reps","distance_miles","duration_seconds","rpe"\n'
    '"Pull","5 Sep 2026, 07:30","5 Sep 2026, 08:15","","Deadlift (Barbell)","","","0","warmup","135","5","","",""\n'
    '"Pull","5 Sep 2026, 07:30","5 Sep 2026, 08:15","","Deadlift (Barbell)","","","1","normal","315","3","","","9"\n'
    '"Pull","5 Sep 2026, 07:30","5 Sep 2026, 08:15","","Lat Pulldown (Cable)","","","0","normal","120","10","","",""\n'
    '"Pull","5 Sep 2026, 07:30","5 Sep 2026, 08:15","","Running","","","0","normal","","","2","1200",""\n'
)


def post_import(client: TestClient, headers: dict, csv: str, unit: str | None = "kg"):
    return client.post(IMPORT, json={"csv": csv, "unit": unit}, headers=headers)


# ---------------------------------------------------------------------------
# Parsing (no database)
# ---------------------------------------------------------------------------


def test_a_strong_export_parses_into_workouts() -> None:
    parsed = importer.parse(STRONG_CSV, unit="kg", tz_name="Asia/Kolkata", now=NOW)
    assert parsed.source == importer.STRONG
    push, legs = parsed.workouts
    assert push.name == "Push Day"
    # 18:00 in Kolkata is 12:30 UTC; the duration sets the end.
    assert push.started_at == dt.datetime(2026, 9, 1, 12, 30, tzinfo=dt.timezone.utc)
    assert push.ended_at - push.started_at == dt.timedelta(minutes=65)
    # The rest timer is not a set.
    assert [s.exercise_name for s in push.sets] == [
        "Bench Press (Barbell)", "Bench Press (Barbell)", "Bench Press (Barbell)", "Cable Kickback (Cable)"
    ]
    assert push.sets[0].is_warmup and not push.sets[1].is_warmup
    assert push.sets[1].rpe == Decimal("8.0")
    # The plank is a timed set; the empty squat row is skipped.
    plank = legs.sets[-1]
    assert plank.reps is None and plank.duration_seconds == 60
    assert parsed.skipped_rows == 1


def test_strong_weights_follow_the_chosen_unit() -> None:
    parsed = importer.parse(STRONG_CSV, unit="lb", tz_name="UTC", now=NOW)
    assert parsed.workouts[0].sets[1].weight_kg == Decimal("36.29")  # 80 lb


def test_a_hevy_export_parses_pounds_and_miles() -> None:
    parsed = importer.parse(HEVY_CSV, unit="kg", tz_name="UTC", now=NOW)
    assert parsed.source == importer.HEVY
    [pull] = parsed.workouts
    assert pull.ended_at - pull.started_at == dt.timedelta(minutes=45)
    warmup, top, pulldown, run = pull.sets
    assert warmup.is_warmup
    assert top.weight_kg == Decimal("142.88")  # 315 lb
    assert top.rpe == Decimal("9.0")
    assert run.distance_m == Decimal("3218.69")  # 2 miles
    assert run.duration_seconds == 1200


def test_future_rows_are_skipped() -> None:
    parsed = importer.parse(STRONG_CSV, unit="kg", tz_name="UTC", now=dt.datetime(2026, 9, 2, tzinfo=dt.timezone.utc))
    assert [w.name for w in parsed.workouts] == ["Push Day"]


def test_names_match_the_library_only_when_the_equipment_agrees() -> None:
    def entry(equipment: str) -> importer.LibraryEntry:
        return importer.LibraryEntry(uuid.uuid4(), equipment)

    library = {
        "back-squat": entry("barbell"),
        "barbell-bench-press": entry("barbell"),
        "lat-pulldown": entry("cable"),
        "tricep-pushdown": entry("cable"),
        "pull-up": entry("bodyweight"),
        "barbell-curl": entry("barbell"),
    }
    match = lambda name: importer.match_library(name, library)  # noqa: E731
    assert match("Squat (Barbell)") is library["back-squat"]
    assert match("Bench Press (Barbell)") is library["barbell-bench-press"]
    assert match("Lat Pulldown (Cable)") is library["lat-pulldown"]
    assert match("Triceps Pushdown (Cable)") is library["tricep-pushdown"]
    assert match("Bicep Curl (Barbell)") is library["barbell-curl"]
    assert match("Pull Up (Assisted)") is library["pull-up"]
    # A Smith machine squat is not the barbell Back Squat (or its rank trial).
    assert match("Squat (Smith Machine)") is None
    assert match("Cable Kickback (Cable)") is None


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------


def test_an_import_builds_history_records_and_xp(client: TestClient, auth: dict, db: Session) -> None:
    r = post_import(client, auth, STRONG_CSV)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "strong"
    assert body["workouts_imported"] == 2
    assert body["sets_imported"] == 7
    assert body["rows_skipped"] == 1
    assert sorted(body["exercises_created"]) == ["Cable Kickback (Cable)", "Squat (Smith Machine)"]
    assert body["xp_awarded"] == 2 * importer.XP_PER_WORKOUT
    assert body["progression"]["xp_awarded"] == 2 * importer.XP_PER_WORKOUT
    assert not body["duplicate"]

    sessions = db.scalars(select(WorkoutSession).order_by(WorkoutSession.started_at)).all()
    assert [s.name for s in sessions] == ["Push Day", "Legs"]
    assert all(s.status == "completed" and s.qualified is False and s.import_id for s in sessions)

    # The heaviest bench came from the file, dated to its workout.
    best = db.scalar(
        select(func.max(PersonalRecord.value)).where(
            PersonalRecord.session_id == sessions[0].id,
            PersonalRecord.record_type == RecordType.MAX_WEIGHT.value,
        )
    )
    assert best == Decimal("82.50")

    history = client.get("/api/v1/workouts/sessions", headers=auth).json()
    assert {s["name"] for s in history} == {"Push Day", "Legs"}


def test_imports_pay_no_points_and_no_streak(client: TestClient, auth: dict) -> None:
    assert post_import(client, auth, STRONG_CSV).status_code == 200
    progress = client.get("/api/v1/auth/me", headers=auth).json()["progress"]
    assert progress["points_balance"] == 0
    assert progress["total_xp"] == 2 * importer.XP_PER_WORKOUT
    points = client.get("/api/v1/workouts/points", headers=auth).json()
    assert points["this_week_points"] == 0


def test_the_same_file_imports_once(client: TestClient, auth: dict, db: Session) -> None:
    assert post_import(client, auth, STRONG_CSV).status_code == 200
    again = post_import(client, auth, STRONG_CSV).json()
    assert again["duplicate"]
    assert again["workouts_imported"] == 0 and again["xp_awarded"] == 0
    assert db.scalar(select(func.count(WorkoutSession.id))) == 2
    assert db.scalar(select(func.count(WorkoutImport.id))) == 1


def test_a_newer_export_only_adds_new_workouts(client: TestClient, auth: dict, db: Session) -> None:
    assert post_import(client, auth, STRONG_CSV).status_code == 200
    newer = post_import(client, auth, STRONG_NEWER).json()
    assert newer["workouts_imported"] == 1
    assert newer["workouts_skipped"] == 2
    # Exercises the first import created are reused, not duplicated.
    assert newer["exercises_created"] == []
    assert db.scalar(select(func.count(WorkoutSession.id))) == 3


def test_a_hevy_import_matches_library_lifts(client: TestClient, auth: dict) -> None:
    body = post_import(client, auth, HEVY_CSV, unit=None).json()
    assert body["source"] == "hevy"
    assert body["sets_imported"] == 4
    # Deadlift, lat pulldown and running are all library exercises.
    assert body["exercises_created"] == []


def test_an_imported_lift_can_pass_a_rank_trial(client: TestClient, auth: dict) -> None:
    bodyweight = client.post(
        "/api/v1/body-measurements", json={"metric": "weight", "value": 80, "unit": "kg"}, headers=auth
    )
    assert bodyweight.status_code == 201, bodyweight.text
    assert post_import(client, auth, STRONG_CSV).status_code == 200
    trials = {t["rank"]: t for t in client.get("/api/v1/profile/trials", headers=auth).json()}
    assert trials["B"]["passed"]
    assert client.get("/api/v1/auth/me", headers=auth).json()["progress"]["trials_passed"] == "B"


def test_a_file_that_is_not_an_export_is_refused(client: TestClient, auth: dict) -> None:
    r = post_import(client, auth, "name,value\nfoo,1\n")
    assert r.status_code == 422
    assert "Strong or Hevy" in r.json()["detail"]
