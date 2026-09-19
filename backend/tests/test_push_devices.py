"""Registering devices for server push, and every way they come off again."""

import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.devices import MAX_DEVICES_PER_USER
from app.models.push_device import PushDevice
from tests.conftest import unique_email

SIGNUP = "/api/v1/auth/signup"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
LOGOUT_ALL = "/api/v1/auth/logout-all"
ME = "/api/v1/auth/me"
PUSH = "/api/v1/devices/push-token"
PASSWORD = "correct-horse-1"


def _signup_and_login(client: TestClient) -> tuple[str, dict]:
    email = unique_email()
    signup = client.post(SIGNUP, json={"email": email, "password": PASSWORD, "display_name": "Sung"})
    assert signup.status_code == 201, signup.text
    return email, _login(client, email)


def _login(client: TestClient, email: str) -> dict:
    r = client.post(LOGIN, json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


def _bearer(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _session_id(tokens: dict) -> uuid.UUID:
    claims = jwt.decode(tokens["access_token"], options={"verify_signature": False})
    return uuid.UUID(claims["sid"])


def _token() -> str:
    """A fresh 32-byte token as hex, the shape iOS hands out today."""
    return uuid.uuid4().hex + uuid.uuid4().hex


def _register(client: TestClient, tokens: dict, token: str, environment: str = "production") -> None:
    r = client.put(PUSH, headers=_bearer(tokens), json={"token": token, "environment": environment})
    assert r.status_code == 204, r.text


def _rows(db: Session, **where) -> list[PushDevice]:
    db.expire_all()
    query = select(PushDevice)
    for column, value in where.items():
        query = query.where(getattr(PushDevice, column) == value)
    return list(db.scalars(query))


def _user_id(client: TestClient, tokens: dict) -> uuid.UUID:
    return uuid.UUID(client.get(ME, headers=_bearer(tokens)).json()["id"])


def test_registering_ties_the_token_to_this_user_and_session(client: TestClient, db: Session) -> None:
    _, tokens = _signup_and_login(client)
    token = _token()
    _register(client, tokens, token, "sandbox")

    [row] = _rows(db, token=token)
    assert row.user_id == _user_id(client, tokens)
    assert row.session_id == _session_id(tokens)
    assert row.environment == "sandbox"


def test_the_old_printed_spelling_is_the_same_device(client: TestClient, db: Session) -> None:
    _, tokens = _signup_and_login(client)
    token = _token()
    # "<A1B2C3D4 ...>" - how older iOS code printed the token's bytes.
    spaced = "<" + " ".join(token[i : i + 8] for i in range(0, len(token), 8)).upper() + ">"
    _register(client, tokens, spaced)
    _register(client, tokens, token)

    assert [row.token for row in _rows(db, user_id=_user_id(client, tokens))] == [token]


def test_registering_again_refreshes_rather_than_duplicates(client: TestClient, db: Session) -> None:
    _, tokens = _signup_and_login(client)
    token = _token()
    _register(client, tokens, token, "sandbox")
    [first] = _rows(db, token=token)
    first_seen = first.updated_at

    _register(client, tokens, token, "production")
    [again] = _rows(db, token=token)
    assert again.environment == "production"
    assert again.updated_at > first_seen


def test_a_second_account_on_the_same_phone_takes_the_token_over(client: TestClient, db: Session) -> None:
    _, first = _signup_and_login(client)
    _, second = _signup_and_login(client)
    token = _token()
    _register(client, first, token)
    _register(client, second, token)

    [row] = _rows(db, token=token)
    assert row.user_id == _user_id(client, second)
    assert row.session_id == _session_id(second)


def test_the_least_recently_registered_device_goes_past_the_cap(client: TestClient, db: Session) -> None:
    _, tokens = _signup_and_login(client)
    tokens_in_order = [_token() for _ in range(MAX_DEVICES_PER_USER + 1)]
    for token in tokens_in_order:
        _register(client, tokens, token)

    kept = {row.token for row in _rows(db, user_id=_user_id(client, tokens))}
    assert kept == set(tokens_in_order[1:])


def test_a_malformed_registration_is_rejected(client: TestClient) -> None:
    _, tokens = _signup_and_login(client)
    for body in (
        {"token": "not-a-device-token-at-all", "environment": "production"},
        {"token": _token()[:-1], "environment": "production"},  # odd length
        {"token": "abcd", "environment": "production"},  # too short
        {"token": _token(), "environment": "staging"},
    ):
        r = client.put(PUSH, headers=_bearer(tokens), json=body)
        assert r.status_code == 422, (body, r.text)


def test_registering_needs_a_signed_in_user(client: TestClient) -> None:
    r = client.put(PUSH, json={"token": _token(), "environment": "production"})
    assert r.status_code == 401


def test_unregistering_removes_only_your_own_token(client: TestClient, db: Session) -> None:
    _, mine = _signup_and_login(client)
    _, theirs = _signup_and_login(client)
    my_token, their_token = _token(), _token()
    _register(client, mine, my_token)
    _register(client, theirs, their_token)

    assert client.delete(f"{PUSH}/{their_token}", headers=_bearer(mine)).status_code == 204
    assert len(_rows(db, token=their_token)) == 1

    assert client.delete(f"{PUSH}/{my_token}", headers=_bearer(mine)).status_code == 204
    assert _rows(db, token=my_token) == []
    # Again, for a retry after a lost reply.
    assert client.delete(f"{PUSH}/{my_token}", headers=_bearer(mine)).status_code == 204


def test_unregistering_a_malformed_token_is_rejected(client: TestClient) -> None:
    _, tokens = _signup_and_login(client)
    assert client.delete(f"{PUSH}/not-hex", headers=_bearer(tokens)).status_code == 422


def test_signing_out_of_one_device_stops_only_its_notifications(client: TestClient, db: Session) -> None:
    email, phone = _signup_and_login(client)
    tablet = _login(client, email)
    phone_token, tablet_token = _token(), _token()
    _register(client, phone, phone_token)
    _register(client, tablet, tablet_token)

    assert client.post(LOGOUT, headers=_bearer(phone)).status_code == 204

    assert _rows(db, token=phone_token) == []
    assert len(_rows(db, token=tablet_token)) == 1


def test_signing_out_with_the_refresh_token_also_stops_them(client: TestClient, db: Session) -> None:
    _, tokens = _signup_and_login(client)
    token = _token()
    _register(client, tokens, token)

    r = client.post(LOGOUT, json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 204, r.text
    assert _rows(db, token=token) == []


def test_signing_out_everywhere_stops_every_device(client: TestClient, db: Session) -> None:
    email, phone = _signup_and_login(client)
    tablet = _login(client, email)
    user_id = _user_id(client, phone)
    _register(client, phone, _token())
    _register(client, tablet, _token())

    assert client.post(LOGOUT_ALL, headers=_bearer(phone)).status_code == 204
    assert _rows(db, user_id=user_id) == []


def test_deleting_the_account_removes_its_devices(client: TestClient, db: Session) -> None:
    _, tokens = _signup_and_login(client)
    user_id = _user_id(client, tokens)
    _register(client, tokens, _token())

    r = client.request("DELETE", ME, headers=_bearer(tokens), json={"password": PASSWORD})
    assert r.status_code == 204, r.text
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(PushDevice).where(PushDevice.user_id == user_id)) == 0
