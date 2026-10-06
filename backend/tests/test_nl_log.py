"""Natural-language logging over HTTP: parse is side-effect free, a confirmed
set goes through the ordinary log-set path, the LLM fallback is constrained,
feedback teaches aliases. The LLM is always mocked - no test calls the API."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import nl_llm
from app.core.config import get_settings
from app.models.nl_log import ExerciseAlias, ParseLog
from app.models.workout import PointsLedgerEntry, SetEntry
from tests.test_workouts import BENCH, SQUAT, WK, exercise_id, log, start

PARSE = "/api/v1/log/parse"
ALIASES = "/api/v1/exercises/aliases"


def parse(client: TestClient, auth: dict, text: str, **extra) -> dict:
    r = client.post(PARSE, json={"text": text, **extra}, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch):
    """Switch the fallback on and script its answer."""
    calls: list[str] = []

    def _set(answer: dict | None):
        monkeypatch.setattr(get_settings(), "anthropic_api_key", "test-key")

        def fake(text, ctx):
            calls.append(text)
            return answer

        monkeypatch.setattr(nl_llm, "_call", fake)
        return calls

    return _set


def test_parse_proposes_and_logs_nothing(client: TestClient, user_factory, db: Session) -> None:
    auth, user = user_factory()
    session = start(client, auth)
    got = parse(client, auth, "bench 80 for 8", session_id=session["id"])

    assert got["parser_used"] == "grammar"
    assert got["set_count"] == 1
    proposed = got["proposed_sets"][0]
    assert proposed["exercise_name"] == BENCH
    assert (proposed["weight"], proposed["unit"], proposed["reps"]) == (80, "kg", 8)
    assert got["problem"] is None
    uid = uuid.UUID(user["id"])
    assert db.scalar(select(func.count(SetEntry.id)).where(SetEntry.user_id == uid)) == 0
    assert db.scalar(select(func.count(PointsLedgerEntry.id)).where(PointsLedgerEntry.user_id == uid)) == 0
    assert db.scalar(select(func.count(ParseLog.id)).where(ParseLog.user_id == uid)) == 1


def test_a_confirmed_proposal_logs_like_any_other_set(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    proposed = parse(client, auth, "squat 100 for 5", session_id=session["id"])["proposed_sets"][0]
    logged = log(
        client, auth, session["id"], proposed["exercise_id"],
        weight=proposed["weight"], reps=proposed["reps"], unit=proposed["unit"],
    )
    assert logged["set"]["weight_kg"] == 100
    assert logged["pr_events"], "records are judged exactly as for a tapped set"


def test_same_again_repeats_the_sessions_last_set(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    bench = exercise_id(client, auth, BENCH)
    log(client, auth, session["id"], bench, weight=90, reps=4)
    got = parse(client, auth, "same again", session_id=session["id"])
    assert (got["proposed_sets"][0]["weight"], got["proposed_sets"][0]["reps"]) == (90, 4)
    assert got["proposed_sets"][0]["exercise_id"] == bench


def test_the_current_card_is_the_default_exercise(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    squat = exercise_id(client, auth, SQUAT)
    got = parse(client, auth, "100 for 5", session_id=session["id"], exercise_id=squat)
    assert got["proposed_sets"][0]["exercise_id"] == squat


def test_nonsense_is_an_answer_not_an_error(client: TestClient, auth: dict) -> None:
    got = parse(client, auth, "the weather is nice")
    assert got["proposed_sets"] == [] and got["parser_used"] == "none"
    assert got["problem"]


def test_another_users_session_is_404(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    theirs, _ = user_factory()
    session = start(client, mine)
    r = client.post(PARSE, json={"text": "80 for 8", "session_id": session["id"]}, headers=theirs)
    assert r.status_code == 404


# --- the LLM fallback ---------------------------------------------------------


def test_the_llm_is_only_asked_when_the_grammar_fails(client: TestClient, auth: dict, llm) -> None:
    calls = llm(None)
    parse(client, auth, "bench 80 for 8")
    assert calls == []


def test_the_llm_answer_is_used_when_valid(client: TestClient, auth: dict, llm) -> None:
    squat = exercise_id(client, auth, SQUAT)
    llm({"understood": True, "exercise_id": squat, "weight": 100, "unit": "kg", "reps": 5,
         "sets": 2, "rpe": None, "is_warmup": False})
    got = parse(client, auth, "did a couple heavy ones on legs, a ton for five")
    assert got["parser_used"] == "llm"
    assert got["set_count"] == 2
    assert got["proposed_sets"][0]["exercise_id"] == squat


def test_the_llm_cannot_invent_an_exercise(client: TestClient, auth: dict, llm) -> None:
    llm({"understood": True, "exercise_id": str(uuid.uuid4()), "weight": 100, "unit": "kg",
         "reps": 5, "sets": 1, "rpe": None, "is_warmup": False})
    got = parse(client, auth, "something only a model would read")
    assert got["proposed_sets"] == [] and got["parser_used"] == "none"


def test_the_llm_answer_is_held_to_the_same_bounds(client: TestClient, auth: dict, llm) -> None:
    squat = exercise_id(client, auth, SQUAT)
    llm({"understood": True, "exercise_id": squat, "weight": 5000, "unit": "kg", "reps": 5,
         "sets": 1, "rpe": None, "is_warmup": False})
    assert parse(client, auth, "loads on legs, felt strong")["proposed_sets"] == []


def test_an_llm_failure_is_a_clean_couldnt_parse(client: TestClient, auth: dict, llm) -> None:
    llm(None)  # timeout, refusal, bad JSON - all arrive as None
    got = parse(client, auth, "hmm")
    assert got["proposed_sets"] == [] and got["problem"]


# --- feedback and aliases -----------------------------------------------------


def test_feedback_is_recorded_once(client: TestClient, auth: dict) -> None:
    got = parse(client, auth, "bench 80 for 8")
    url = f"{PARSE}/{got['parse_id']}/feedback"
    assert client.post(url, json={"accepted": True}, headers=auth).status_code == 200
    assert client.post(url, json={"accepted": True}, headers=auth).status_code == 409


def test_correcting_the_same_phrase_twice_learns_an_alias(
    client: TestClient, auth: dict, db: Session
) -> None:
    squat = exercise_id(client, auth, SQUAT)
    learned = []
    for _ in range(2):
        got = parse(client, auth, "zercher thing 100 for 5")
        r = client.post(
            f"{PARSE}/{got['parse_id']}/feedback",
            json={"accepted": False, "corrected_result": {
                "exercise_id": squat, "weight": 100, "unit": "kg", "reps": 5}},
            headers=auth,
        )
        learned.append(r.json()["alias_learned"])
    assert learned == [False, True]
    again = parse(client, auth, "zercher thing 100 for 5")
    assert again["proposed_sets"][0]["exercise_id"] == squat
    assert again["exercise_confidence"] == 1.0


def test_aliases_can_be_listed_and_added(client: TestClient, auth: dict) -> None:
    shipped = client.get(ALIASES, headers=auth).json()
    assert any(a["alias"] == "bench" and a["source"] == "seed" for a in shipped)

    bench = exercise_id(client, auth, BENCH)
    r = client.post(ALIASES, json={"alias": "Flat BB", "exercise_id": bench}, headers=auth)
    assert r.status_code == 201 and r.json()["alias"] == "flat bb"
    assert client.post(ALIASES, json={"alias": "flat bb", "exercise_id": bench}, headers=auth).status_code == 409
    assert parse(client, auth, "flat bb 80 for 8")["proposed_sets"][0]["exercise_id"] == bench


def test_a_personal_alias_is_private(client: TestClient, user_factory, db: Session) -> None:
    mine, _ = user_factory()
    theirs, _ = user_factory()
    squat = exercise_id(client, mine, SQUAT)
    client.post(ALIASES, json={"alias": "leg day lift", "exercise_id": squat}, headers=mine)
    assert all(a["alias"] != "leg day lift" for a in client.get(ALIASES, headers=theirs).json())
    assert db.scalar(
        select(func.count(ExerciseAlias.id)).where(ExerciseAlias.alias == "leg day lift")
    ) == 1
