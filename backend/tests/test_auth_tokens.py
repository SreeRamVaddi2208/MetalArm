"""Refresh tokens, device sessions, sign-out, and account deletion."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, normalize_email
from app.models.auth_session import AuthSession
from app.models.party import Party
from app.models.user import User
from tests.conftest import unique_email

settings = get_settings()
SIGNUP = "/api/v1/auth/signup"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
LOGOUT_ALL = "/api/v1/auth/logout-all"
ME = "/api/v1/auth/me"
PASSWORD = "correct-horse-1"


def _signup_and_login(client: TestClient) -> tuple[str, dict]:
    email = unique_email()
    signup = client.post(SIGNUP, json={"email": email, "password": PASSWORD, "display_name": "Sung"})
    assert signup.status_code == 201, signup.text
    login = client.post(LOGIN, json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return email, login.json()


def _login(client: TestClient, email: str) -> dict:
    r = client.post(LOGIN, json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


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


def test_logout_ends_only_this_device(client: TestClient) -> None:
    email, phone = _signup_and_login(client)
    laptop = _login(client, email)

    assert client.post(LOGOUT, headers=_bearer(phone["access_token"])).status_code == 204

    # The phone's tokens stop working at once...
    assert client.get(ME, headers=_bearer(phone["access_token"])).status_code == 401
    assert client.post(REFRESH, json={"refresh_token": phone["refresh_token"]}).status_code == 401
    # ...while the laptop stays signed in.
    assert client.get(ME, headers=_bearer(laptop["access_token"])).status_code == 200
    assert client.post(REFRESH, json={"refresh_token": laptop["refresh_token"]}).status_code == 200


def test_refreshed_tokens_stay_on_the_same_device_session(client: TestClient) -> None:
    _, tokens = _signup_and_login(client)
    renewed = client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]}).json()

    assert client.post(LOGOUT, headers=_bearer(renewed["access_token"])).status_code == 204

    # Signing out with the renewed token also ends the original refresh token:
    # they belong to one device session.
    assert client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    assert client.post(REFRESH, json={"refresh_token": renewed["refresh_token"]}).status_code == 401


def test_logout_with_the_refresh_token_needs_no_access_token(client: TestClient) -> None:
    email, phone = _signup_and_login(client)
    laptop = _login(client, email)

    # What a client does once its access token has expired: sign out with the
    # refresh token alone.
    assert client.post(LOGOUT, json={"refresh_token": phone["refresh_token"]}).status_code == 204

    assert client.get(ME, headers=_bearer(phone["access_token"])).status_code == 401
    assert client.post(REFRESH, json={"refresh_token": phone["refresh_token"]}).status_code == 401
    assert client.get(ME, headers=_bearer(laptop["access_token"])).status_code == 200
    # Signing out again is harmless.
    assert client.post(LOGOUT, json={"refresh_token": phone["refresh_token"]}).status_code == 204


def test_logout_needs_a_valid_token(client: TestClient) -> None:
    _, tokens = _signup_and_login(client)
    assert client.post(LOGOUT).status_code == 401
    assert client.post(LOGOUT, json={"refresh_token": "not.a.jwt"}).status_code == 401
    # An access token in the body is not a refresh token.
    assert client.post(LOGOUT, json={"refresh_token": tokens["access_token"]}).status_code == 401


def _pre_session_tokens(db: Session, email: str) -> tuple[str, str]:
    """Tokens as minted before device sessions existed: no `sid` claim."""
    user = db.scalar(select(User).where(User.email_normalized == normalize_email(email)))
    assert user is not None
    return (
        create_access_token(user.id, user.token_version)[0],
        create_refresh_token(user.id, user.token_version)[0],
    )


def test_refresh_rejects_tokens_from_before_device_sessions(client: TestClient, db: Session) -> None:
    email, _ = _signup_and_login(client)
    _, old_refresh = _pre_session_tokens(db, email)
    assert client.post(REFRESH, json={"refresh_token": old_refresh}).status_code == 401


def test_logout_with_a_pre_session_token_revokes_it(client: TestClient, db: Session) -> None:
    email, _ = _signup_and_login(client)
    old_access, _ = _pre_session_tokens(db, email)
    assert client.get(ME, headers=_bearer(old_access)).status_code == 200

    # No session to revoke, so sign-out ends every token issued so far
    # rather than reporting success while the token keeps working.
    assert client.post(LOGOUT, headers=_bearer(old_access)).status_code == 204
    assert client.get(ME, headers=_bearer(old_access)).status_code == 401


def test_logout_all_ends_every_device(client: TestClient) -> None:
    email, phone = _signup_and_login(client)
    laptop = _login(client, email)

    assert client.post(LOGOUT_ALL, headers=_bearer(phone["access_token"])).status_code == 204

    for device in (phone, laptop):
        assert client.get(ME, headers=_bearer(device["access_token"])).status_code == 401
        assert client.post(REFRESH, json={"refresh_token": device["refresh_token"]}).status_code == 401

    # Signing in again works and yields tokens for the new version.
    fresh = _login(client, email)
    assert client.get(ME, headers=_bearer(fresh["access_token"])).status_code == 200


def test_delete_account_requires_the_password(client: TestClient) -> None:
    _, tokens = _signup_and_login(client)
    r = client.request("DELETE", ME, headers=_bearer(tokens["access_token"]), json={"password": "wrong-pass-9"})
    assert r.status_code == 403
    assert client.get(ME, headers=_bearer(tokens["access_token"])).status_code == 200


def test_delete_account_removes_the_user_and_its_sessions(client: TestClient, db: Session) -> None:
    email, tokens = _signup_and_login(client)
    _login(client, email)
    user_id = client.get(ME, headers=_bearer(tokens["access_token"])).json()["id"]

    r = client.request("DELETE", ME, headers=_bearer(tokens["access_token"]), json={"password": PASSWORD})
    assert r.status_code == 204, r.text

    assert client.get(ME, headers=_bearer(tokens["access_token"])).status_code == 401
    assert client.post(LOGIN, json={"email": email, "password": PASSWORD}).status_code == 401
    db.expire_all()
    assert db.get(User, user_id) is None
    remaining = db.scalar(select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user_id))
    assert remaining == 0


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
