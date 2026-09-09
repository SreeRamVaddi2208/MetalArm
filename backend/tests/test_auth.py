"""Auth: signup, login, token handling."""

import datetime as dt

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.conftest import unique_email

settings = get_settings()
SIGNUP = "/api/v1/auth/signup"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def test_signup_creates_user_with_initial_progress(client: TestClient) -> None:
    r = client.post(
        SIGNUP,
        json={
            "email": unique_email(),
            "password": "correct-horse-1",
            "display_name": "Sung",
            "timezone": "America/New_York",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # A user must never exist without a progression row.
    assert body["progress"]["current_level"] == 1
    assert body["progress"]["rank"] == "E"
    assert body["progress"]["total_xp"] == 0


def test_signup_never_returns_the_password_hash(client: TestClient) -> None:
    r = client.post(
        SIGNUP,
        json={
            "email": unique_email(),
            "password": "correct-horse-1",
            "display_name": "Sung",
        },
    )
    assert "password_hash" not in r.text
    assert "password" not in r.json()


def test_duplicate_email_is_rejected_case_insensitively(client: TestClient) -> None:
    email = unique_email()
    first = client.post(
        SIGNUP,
        json={"email": email, "password": "correct-horse-1", "display_name": "A"},
    )
    assert first.status_code == 201
    second = client.post(
        SIGNUP,
        json={
            "email": email.upper(),
            "password": "different-pass-2",
            "display_name": "B",
        },
    )
    assert second.status_code == 409


@pytest.mark.parametrize(
    "field,value",
    [
        ("password", "short"),          # below the 8-char minimum
        ("password", "x" * 73),         # over bcrypt's 72-BYTE ceiling
        ("timezone", "Mars/Olympus"),   # not a real IANA zone
        ("display_name", ""),           # empty
        ("email", "not-an-email"),
    ],
)
def test_signup_rejects_invalid_input(client: TestClient, field: str, value: str) -> None:
    payload = {
        "email": unique_email(),
        "password": "correct-horse-1",
        "display_name": "Sung",
        "timezone": "UTC",
    }
    payload[field] = value
    r = client.post(SIGNUP, json=payload)
    # 422, never a 500 - bcrypt raises on >72 bytes, so the schema must catch it.
    assert r.status_code == 422, r.text


def test_multibyte_password_is_measured_in_bytes(client: TestClient) -> None:
    """30 emoji are 120 UTF-8 bytes, so this must be rejected even though it is
    well under 72 CHARACTERS."""
    r = client.post(
        SIGNUP,
        json={
            "email": unique_email(),
            "password": "🗡" * 30,
            "display_name": "Sung",
        },
    )
    assert r.status_code == 422
    assert "bytes" in r.text


def test_login_succeeds_with_case_variant_email(client: TestClient) -> None:
    email = unique_email()
    client.post(
        SIGNUP,
        json={"email": email, "password": "correct-horse-1", "display_name": "Sung"},
    )
    r = client.post(LOGIN, json={"email": email.upper(), "password": "correct-horse-1"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"


def test_wrong_password_and_unknown_email_are_indistinguishable(
    client: TestClient,
) -> None:
    """Identical status AND body: any difference turns login into an
    account-existence oracle."""
    email = unique_email()
    client.post(
        SIGNUP,
        json={"email": email, "password": "correct-horse-1", "display_name": "Sung"},
    )
    wrong_pw = client.post(LOGIN, json={"email": email, "password": "nope-nope-nope"})
    unknown = client.post(LOGIN, json={"email": unique_email(), "password": "nope-nope-nope"})

    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


def test_me_requires_a_token(client: TestClient) -> None:
    assert client.get(ME).status_code == 401


def test_me_returns_the_authenticated_user(client: TestClient, user_factory) -> None:
    headers, created = user_factory()
    r = client.get(ME, headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def _forge(secret: str, algorithm: str = "HS256", **overrides) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "iat": now,
        "exp": now + dt.timedelta(hours=1),
    }
    payload.update(overrides)
    return jwt.encode(payload, secret, algorithm=algorithm)


def test_token_signed_with_the_wrong_secret_is_rejected(client: TestClient) -> None:
    token = _forge("attacker-guessed-secret")
    r = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_alg_none_token_is_rejected(client: TestClient) -> None:
    """The classic algorithm-confusion attack: an unsigned token must never
    authenticate. decode() pins `algorithms` to the configured one."""
    token = jwt.encode({"sub": "00000000-0000-0000-0000-000000000001"}, "", algorithm="none")
    r = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_expired_token_is_rejected(client: TestClient) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "iat": now - dt.timedelta(hours=3),
            "exp": now - dt.timedelta(hours=2),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    r = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert "expired" in r.json()["detail"].lower()


def test_valid_token_for_a_deleted_user_is_rejected(client: TestClient) -> None:
    """A correctly signed token whose subject no longer exists must not
    authenticate."""
    token = _forge(settings.jwt_secret_key, settings.jwt_algorithm)
    r = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_garbage_token_is_rejected(client: TestClient) -> None:
    r = client.get(ME, headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401
