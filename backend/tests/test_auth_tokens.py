"""Refresh tokens, sign-out everywhere, and account deletion."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.party import Party
from app.models.user import User
from tests.conftest import unique_email

settings = get_settings()
SIGNUP = "/api/v1/auth/signup"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"
PASSWORD = "correct-horse-1"


def _signup_and_login(client: TestClient) -> tuple[str, dict]:
    email = unique_email()
    signup = client.post(SIGNUP, json={"email": email, "password": PASSWORD, "display_name": "Sung"})
    assert signup.status_code == 201, signup.text
    login = client.post(LOGIN, json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return email, login.json()


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_a_refresh_token(client: TestClient) -> None:
    _, tokens = _signup_and_login(client)
    assert tokens["refresh_token"]
    assert tokens["refresh_expires_in"] == settings.refresh_token_expire_days * 86400
    assert tokens["expires_in"] == settings.access_token_expire_minutes * 60


def test_refresh_returns_a_working_pair(client: TestClient) -> None:
    _, tokens = _signup_and_login(client)
    r = client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200, r.text
    assert client.get(ME, headers=_bearer(r.json()["access_token"])).status_code == 200


def test_refresh_token_is_not_accepted_as_an_access_token(client: TestClient) -> None:
    _, tokens = _signup_and_login(client)
    assert client.get(ME, headers=_bearer(tokens["refresh_token"])).status_code == 401


def test_access_token_cannot_be_used_to_refresh(client: TestClient) -> None:
    _, tokens = _signup_and_login(client)
    r = client.post(REFRESH, json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401


def test_garbage_refresh_token_is_rejected(client: TestClient) -> None:
    assert client.post(REFRESH, json={"refresh_token": "not.a.jwt"}).status_code == 401


def test_logout_revokes_every_issued_token(client: TestClient) -> None:
    email, tokens = _signup_and_login(client)
    assert client.post(LOGOUT, headers=_bearer(tokens["access_token"])).status_code == 204

    assert client.get(ME, headers=_bearer(tokens["access_token"])).status_code == 401
    assert client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]}).status_code == 401

    # Signing in again works and yields tokens for the new version.
    fresh = client.post(LOGIN, json={"email": email, "password": PASSWORD}).json()
    assert client.get(ME, headers=_bearer(fresh["access_token"])).status_code == 200


def test_delete_account_requires_the_password(client: TestClient) -> None:
    _, tokens = _signup_and_login(client)
    r = client.request("DELETE", ME, headers=_bearer(tokens["access_token"]), json={"password": "wrong-pass-9"})
    assert r.status_code == 403
    assert client.get(ME, headers=_bearer(tokens["access_token"])).status_code == 200


def test_delete_account_removes_the_user(client: TestClient, db: Session) -> None:
    email, tokens = _signup_and_login(client)
    user_id = client.get(ME, headers=_bearer(tokens["access_token"])).json()["id"]

    r = client.request("DELETE", ME, headers=_bearer(tokens["access_token"]), json={"password": PASSWORD})
    assert r.status_code == 204, r.text

    assert client.get(ME, headers=_bearer(tokens["access_token"])).status_code == 401
    assert client.post(LOGIN, json={"email": email, "password": PASSWORD}).status_code == 401
    db.expire_all()
    assert db.get(User, user_id) is None


def test_deleting_a_party_owner_hands_the_party_to_a_member(
    client: TestClient, db: Session, user_factory
) -> None:
    owner_headers, _ = user_factory(password=PASSWORD)
    member_headers, member = user_factory()

    party = client.post("/api/v1/parties", headers=owner_headers, json={"name": "Iron Crew"})
    assert party.status_code == 201, party.text
    party_id = party.json()["id"]
    joined = client.post(
        "/api/v1/parties/join", headers=member_headers, json={"invite_code": party.json()["invite_code"]}
    )
    assert joined.status_code in (200, 201), joined.text

    r = client.request("DELETE", ME, headers=owner_headers, json={"password": PASSWORD})
    assert r.status_code == 204, r.text

    db.expire_all()
    surviving = db.get(Party, party_id)
    assert surviving is not None, "the party was deleted along with its owner"
    assert str(surviving.owner_id) == member["id"]
    assert client.get(f"/api/v1/parties/{party_id}", headers=member_headers).status_code == 200
