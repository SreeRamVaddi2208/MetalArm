"""What the API refuses to store, and what it must keep accepting.

A display name is not private text: it is read by everyone on the league
table, the party board, the activity feed and the share card. So the rules
here are about what a stranger will see, and the tests are named after the
thing each one prevents rather than the rule it exercises.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.text import human_name
from tests.conftest import unique_email

SIGNUP = "/api/v1/auth/signup"
PARTIES = "/api/v1/parties"
QUESTS = "/api/v1/quests"
ROUTINES = "/api/v1/routines"


def signup_body(**overrides) -> dict:
    body = {
        "email": "someone@example.com",
        "password": "correct-horse-1",
        "display_name": "Sree Ram",
        "timezone": "UTC",
    }
    body.update(overrides)
    return body


# --- The rule itself, without a request around it -------------------------


@pytest.mark.parametrize(
    "value,reason",
    [
        ("   ", "a blank name shows as a nameless row on every leaderboard"),
        ("\t\n ", "whitespace of any kind is still blank"),
        ("Sree\x00Ram", "NUL is not typeable; it is pasted or injected"),
        ("Sree\x1bRam", "an escape character can move a terminal's cursor"),
        ("Sree‮Ram", "U+202E reverses the text after it - spoofing, not a typo"),
        ("Sree⁦Ram", "the isolates do the same job more quietly"),
    ],
)
def test_a_name_nobody_should_have_to_read(value: str, reason: str) -> None:
    with pytest.raises(ValueError):
        human_name(value)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("  Sree   Ram  ", "Sree Ram"),   # stray spacing is forgiven, not refused
        ("Sree Ram\n", "Sree Ram"),       # a pasted trailing newline is an accident
        ("José", "José"),
        ("李雷", "李雷"),
        ("O'Brien", "O'Brien"),
        ("Jean-Luc", "Jean-Luc"),
        ("A", "A"),
        ("Ahmed محمد", "Ahmed محمد"),     # right-to-left text needs no override char
    ],
)
def test_a_name_somebody_actually_has(value: str, expected: str) -> None:
    assert human_name(value) == expected


# --- Signing up -----------------------------------------------------------


def test_a_blank_name_cannot_be_registered(client: TestClient) -> None:
    r = client.post(SIGNUP, json=signup_body(display_name="   "))
    assert r.status_code == 422, r.text
    assert "display_name" in r.text and "blank" in r.text


def test_a_spoofing_name_cannot_be_registered(client: TestClient) -> None:
    r = client.post(SIGNUP, json=signup_body(display_name="Sree‮Ram"))
    assert r.status_code == 422, r.text
    assert "RIGHT-TO-LEFT OVERRIDE" in r.text


def test_the_stored_name_is_the_cleaned_one(client: TestClient) -> None:
    email = unique_email()
    created = client.post(SIGNUP, json=signup_body(email=email, display_name="  Sree   Ram "))
    assert created.status_code == 201, created.text
    assert created.json()["display_name"] == "Sree Ram"


@pytest.mark.parametrize(
    "password,why",
    [
        ("12345678", "the first thing anyone tries"),
        ("PassWord", "the same word, differently cased"),
        ("qwerty123", "a keyboard walk"),
        ("someone@example.com", "the address on the form above it"),
        ("someone", "the local part of that address"),
        ("sree ram", "the name on the form above it"),
    ],
)
def test_a_password_that_is_the_first_guess(client: TestClient, password: str, why: str) -> None:
    r = client.post(SIGNUP, json=signup_body(password=password))
    assert r.status_code == 422, f"{why}: {r.text}"


def test_the_password_refusal_reads_as_a_sentence(client: TestClient) -> None:
    """A model-level error has no field name to sit behind.

    FastAPI reports it at loc ("body",), which names nothing on screen, so both
    clients show the message on its own - see frontend/tests/test_api_errors.py
    and APIErrorMessageTests. It therefore has to be a whole sentence rather
    than a clause that only reads correctly after "Password: ".
    """
    r = client.post(SIGNUP, json=signup_body(password="12345678"))
    issue = r.json()["detail"][0]
    assert issue["loc"] == ["body"], issue
    message = issue["msg"].removeprefix("Value error, ")
    assert message[0].isupper(), message
    assert message.endswith("."), message
    assert "password" in message.casefold()


@pytest.mark.parametrize(
    "password",
    [
        "correct-horse-1",
        "three brown bears lifting",   # a long passphrase, spaces and all
        "Tr0ub4dor&3",
    ],
)
def test_a_password_somebody_chose(client: TestClient, password: str) -> None:
    r = client.post(SIGNUP, json=signup_body(email=unique_email(), password=password))
    assert r.status_code == 201, r.text


# --- Everywhere else a name is set ---------------------------------------


def test_a_party_cannot_be_called_nothing(client: TestClient, auth: dict) -> None:
    """Party names are read by everyone in the party."""
    assert client.post(PARTIES, json={"name": "   "}, headers=auth).status_code == 422
    assert client.post(PARTIES, json={"name": "Iron‮Temple"}, headers=auth).status_code == 422
    made = client.post(PARTIES, json={"name": "  Iron   Temple "}, headers=auth)
    assert made.status_code == 201
    assert made.json()["name"] == "Iron Temple"


def test_a_quest_cannot_be_called_nothing(client: TestClient, auth: dict) -> None:
    assert client.post(QUESTS, json={"title": "  ", "xp_reward": 10}, headers=auth).status_code == 422
    made = client.post(QUESTS, json={"title": "  Train   hard ", "xp_reward": 10}, headers=auth)
    assert made.status_code == 201
    assert made.json()["title"] == "Train hard"


def test_a_routine_cannot_be_called_nothing(client: TestClient, auth: dict) -> None:
    assert client.post(ROUTINES, json={"name": " ", "exercises": []}, headers=auth).status_code == 422
    made = client.post(ROUTINES, json={"name": "  Push   day ", "exercises": []}, headers=auth)
    assert made.status_code == 201
    assert made.json()["name"] == "Push day"


def test_a_custom_exercise_cannot_be_called_nothing(client: TestClient, auth: dict) -> None:
    body = {"name": "   ", "category": "strength", "primary_muscle_groups": ["chest"],
            "equipment": "barbell"}
    assert client.post("/api/v1/exercises", json=body, headers=auth).status_code == 422
