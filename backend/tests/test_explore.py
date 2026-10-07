"""Overhaul phase 3: the exercise library as shipped, browsing it, and the
curated programs.

The gate: every library exercise has an illustration (with its credit) and
correct muscles. "Correct" is checked two ways - every code is a real muscle
group, and a table of well-known lifts has the primary muscle a lifter would
name.
"""

import json
from collections import Counter

from fastapi.testclient import TestClient

from app.core import curated, taxonomy
from scripts.import_exercises import DEFAULT_FILE, parse, read_file

A = "/api/v1"
LIBRARY = parse(read_file(DEFAULT_FILE))
BY_SLUG = {row["slug"]: row for row in LIBRARY}
MUSCLES = {m["code"] for m in taxonomy.definitions()["muscle_groups"]}

# slug -> a muscle that MUST be among its primary muscles.
KNOWN = {
    "barbell-bench-press": "chest", "incline-dumbbell-press": "chest", "push-up": "chest",
    "back-squat": "quads", "front-squat": "quads", "leg-press": "quads", "leg-extension": "quads",
    "deadlift": "hamstrings", "romanian-deadlift": "hamstrings", "lying-leg-curl": "hamstrings",
    "barbell-hip-thrust": "glutes", "cable-glute-kickback": "glutes",
    "pull-up": "lats", "lat-pulldown": "lats", "barbell-row": "lats", "seated-cable-row": "lats",
    "overhead-press": "shoulders", "dumbbell-lateral-raise": "shoulders", "push-press": "shoulders",
    "barbell-curl": "biceps", "hammer-curl": "biceps", "ez-bar-curl": "biceps",
    "tricep-pushdown": "triceps", "skull-crusher": "triceps", "rope-triceps-pushdown": "triceps",
    "standing-calf-raise": "calves", "barbell-shrug": "traps", "crunch": "abs",
    "dumbbell-side-bend": "obliques", "good-morning": "hamstrings", "hip-adduction-machine": "adductors",
}


# ---------------------------------------------------------------------------
# The library, as shipped
# ---------------------------------------------------------------------------


def test_every_exercise_has_credited_artwork() -> None:
    missing = [r["name"] for r in LIBRARY if not (r["illustration_url"] and r["thumbnail_url"])]
    assert missing == []
    uncredited = [r["name"] for r in LIBRARY if not (r["media_license"] and r["media_author"])]
    assert uncredited == []
    # Outside work links to where it came from; MetalArm's own diagrams need not.
    unsourced = [r["name"] for r in LIBRARY if r["media_author"] != "MetalArm" and not r["media_source_url"]]
    assert unsourced == []


def test_every_exercise_names_real_muscles() -> None:
    for row in LIBRARY:
        assert row["primary_muscle_groups"], row["name"]
        assert set(row["primary_muscle_groups"]) <= MUSCLES, row["name"]
        assert set(row["secondary_muscle_groups"]) <= MUSCLES, row["name"]
        assert not set(row["primary_muscle_groups"]) & set(row["secondary_muscle_groups"]), row["name"]


def test_well_known_lifts_work_the_right_muscle() -> None:
    wrong = {slug: BY_SLUG[slug]["primary_muscle_groups"] for slug, muscle in KNOWN.items()
             if muscle not in BY_SLUG[slug]["primary_muscle_groups"]}
    assert wrong == {}


def test_the_library_is_broad() -> None:
    # Every browsable muscle tile and equipment circle leads somewhere.
    data = taxonomy.definitions()
    primary = Counter(m for r in LIBRARY for m in r["primary_muscle_groups"])
    for m in data["muscle_groups"]:
        if m["browsable"] and m["code"] not in ("cardio", "neck", "forearms"):
            assert primary[m["code"]] >= 2, m["code"]
    assert len(LIBRARY) >= 190


# ---------------------------------------------------------------------------
# Curated programs, as shipped
# ---------------------------------------------------------------------------


def test_curated_programs_are_real_plans() -> None:
    programs = curated.definitions()
    assert Counter(p["category"] for p in programs) == {"powerlifter": 2, "bodybuilder": 2, "athlete": 2}
    for p in programs:
        assert len(p["routines"]) >= 2 and p["weeks"] > 0 and p["sessions_per_week"] > 0
        for r in p["routines"]:
            assert len(r["exercises"]) >= 3, r["name"]
            for e in r["exercises"]:
                assert e["slug"] in BY_SLUG, e["slug"]
                assert 1 <= e["reps_low"] <= e["reps_high"] and e["sets"] >= 1
    assert len({p["name"] for p in programs}) == len(programs)


# ---------------------------------------------------------------------------
# Browse
# ---------------------------------------------------------------------------


def test_browse_filters_combine(client: TestClient, auth: dict) -> None:
    page = client.get(f"{A}/exercises/browse", params={"muscle": "chest", "limit": 100}, headers=auth).json()
    assert page["total"] == len(page["items"]) > 5
    assert all("chest" in e["primary_muscle_groups"] for e in page["items"])
    both = client.get(f"{A}/exercises/browse", params={"muscle": "chest", "equipment": "dumbbell"},
                      headers=auth).json()
    assert both["total"] < page["total"]
    assert all(e["equipment"] == "dumbbell" for e in both["items"])
    expected = sum(1 for r in LIBRARY if "chest" in r["primary_muscle_groups"] and r["equipment"] == "dumbbell")
    assert both["total"] == expected


def test_browse_search_knows_aliases(client: TestClient, auth: dict) -> None:
    names = [e["name"] for e in client.get(f"{A}/exercises/browse", params={"q": "rdl"}, headers=auth).json()["items"]]
    assert "Romanian Deadlift" in names
    names = [e["name"] for e in client.get(f"{A}/exercises/browse", params={"q": "Lat"}, headers=auth).json()["items"]]
    assert "Lat Pulldown" in names


def test_browse_pages_through_everything_once(client: TestClient, auth: dict) -> None:
    seen, cursor = [], None
    while True:
        page = client.get(f"{A}/exercises/browse", params={"limit": 50, **({"cursor": cursor} if cursor else {})},
                          headers=auth).json()
        seen += [e["id"] for e in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == page["total"] == len(LIBRARY)
    assert client.get(f"{A}/exercises/browse", params={"cursor": "x"}, headers=auth).status_code == 422


def test_browse_includes_my_exercises(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    theirs, _ = user_factory()
    client.post(f"{A}/exercises", json={"name": "Zercher Carry Thing", "category": "strength",
                                        "primary_muscle_groups": ["abs"], "equipment": "barbell"}, headers=mine)
    assert client.get(f"{A}/exercises/browse", params={"q": "zercher"}, headers=mine).json()["total"] == 1
    assert client.get(f"{A}/exercises/browse", params={"q": "zercher"}, headers=theirs).json()["total"] == 0


# ---------------------------------------------------------------------------
# Curated programs over the API
# ---------------------------------------------------------------------------


def test_curated_programs_put_my_path_first(client: TestClient, auth: dict) -> None:
    client.patch(f"{A}/auth/me", json={"character_class": "bodybuilder"}, headers=auth)
    programs = client.get(f"{A}/programs/curated", headers=auth).json()
    assert [p["category"] for p in programs[:2]] == ["bodybuilder", "bodybuilder"] and len(programs) == 6
    athlete = client.get(f"{A}/programs/curated", params={"category": "athlete"}, headers=auth).json()
    assert {p["category"] for p in athlete} == {"athlete"}
    ulb = next(p for p in programs if p["slug"] == "upper-lower-builder")
    upper = ulb["routines"][0]["exercises"]
    assert upper[0]["name"] == "Barbell Bench Press" and (upper[0]["target_reps_low"], upper[0]["target_reps_high"]) == (6, 10)
    assert [e["superset_group"] for e in upper[-2:]] == [1, 1]


def test_saving_a_curated_program_copies_it_once(client: TestClient, auth: dict) -> None:
    r = client.post(f"{A}/programs/curated/peak-strength-block/save", headers=auth)
    assert r.status_code == 201, r.text
    program = r.json()
    assert program["name"] == "Peak Strength Block" and program["owner_user_id"] is not None
    assert [x["name"] for x in program["routines"]] == ["Squat Day", "Bench Day", "Deadlift Day", "Press Day"]
    squat_day = client.get(f"{A}/routines/{program['routines'][0]['id']}", headers=auth).json()
    first = squat_day["exercises"][0]
    assert (first["exercise"]["name"], first["target_sets"], first["target_reps"], first["rest_seconds"]) == (
        "Back Squat", 5, 3, 240)
    assert client.post(f"{A}/programs/curated/peak-strength-block/save", headers=auth).status_code == 409
    listed = {p["slug"]: p for p in client.get(f"{A}/programs/curated", headers=auth).json()}
    assert listed["peak-strength-block"]["saved_program_id"] == program["id"]
    assert client.post(f"{A}/programs/curated/no-such-plan/save", headers=auth).status_code == 404
    # A saved routine starts a workout like any other.
    s = client.post(f"{A}/workouts/sessions", json={"routine_id": program["routines"][1]["id"]}, headers=auth)
    assert s.status_code == 201 and len(s.json()["exercises"]) == 4
