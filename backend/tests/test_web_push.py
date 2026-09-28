"""Web Push subscriptions: the registry, and what happens when one dies."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import web_push
from app.core.config import Settings
from app.models.web_push import WebPushSubscription

SUBSCRIBE = "/api/v1/devices/web-push"
CONFIG = "/api/v1/devices/web-push/config"


def body(endpoint: str = "https://push.example.com/abc") -> dict:
    return {"endpoint": endpoint, "keys": {"p256dh": "BPublicKey", "auth": "AuthSecret"}}


def test_subscribing_needs_a_signed_in_user(client: TestClient) -> None:
    assert client.post(SUBSCRIBE, json=body()).status_code == 401


def test_the_public_key_is_public(client: TestClient) -> None:
    """A browser needs it before it can subscribe, so it cannot require a
    subscription to get it."""
    r = client.get(CONFIG)
    assert r.status_code == 200
    assert "public_key" in r.json()


def test_a_browser_can_subscribe(client: TestClient, auth: dict, db: Session) -> None:
    assert client.post(SUBSCRIBE, json=body(), headers=auth).status_code == 204
    row = db.scalar(select(WebPushSubscription).where(
        WebPushSubscription.endpoint == "https://push.example.com/abc"))
    assert row is not None
    assert row.p256dh == "BPublicKey" and row.auth == "AuthSecret"
    # Bound to the sign-in session, so signing out stops the notifications.
    assert row.session_id is not None


def test_subscribing_twice_refreshes_rather_than_duplicates(
    client: TestClient, auth: dict, db: Session
) -> None:
    """A browser may hand back the same endpoint on every load."""
    client.post(SUBSCRIBE, json=body(), headers=auth)
    refreshed = {"endpoint": "https://push.example.com/abc",
                 "keys": {"p256dh": "BRotatedKey", "auth": "NewSecret"}}
    assert client.post(SUBSCRIBE, json=refreshed, headers=auth).status_code == 204

    db.expire_all()
    rows = db.scalars(select(WebPushSubscription).where(
        WebPushSubscription.endpoint == "https://push.example.com/abc")).all()
    assert len(rows) == 1
    assert rows[0].p256dh == "BRotatedKey"


def test_the_same_browser_moves_between_accounts(
    client: TestClient, user_factory, db: Session
) -> None:
    """The endpoint identifies the browser, not the person: two accounts on one
    browser must not both be notified."""
    first, _ = user_factory()
    second, _ = user_factory()
    client.post(SUBSCRIBE, json=body(), headers=first)
    client.post(SUBSCRIBE, json=body(), headers=second)

    db.expire_all()
    rows = db.scalars(select(WebPushSubscription)).all()
    assert len(rows) == 1
    me = client.get("/api/v1/auth/me", headers=second).json()
    assert str(rows[0].user_id) == me["id"]


def test_unsubscribing_is_idempotent(client: TestClient, auth: dict, db: Session) -> None:
    client.post(SUBSCRIBE, json=body(), headers=auth)
    assert client.request("DELETE", SUBSCRIBE, json=body(), headers=auth).status_code == 204
    # ...and again, on something already gone.
    assert client.request("DELETE", SUBSCRIBE, json=body(), headers=auth).status_code == 204
    assert db.scalar(select(func.count()).select_from(WebPushSubscription)) == 0


def test_you_cannot_unsubscribe_someone_else(
    client: TestClient, user_factory, db: Session
) -> None:
    mine, _ = user_factory()
    theirs, _ = user_factory()
    client.post(SUBSCRIBE, json=body(), headers=mine)
    client.request("DELETE", SUBSCRIBE, json=body(), headers=theirs)
    assert db.scalar(select(func.count()).select_from(WebPushSubscription)) == 1


def test_a_malformed_subscription_is_refused(client: TestClient, auth: dict) -> None:
    assert client.post(SUBSCRIBE, json={"endpoint": "https://p.example/x"}, headers=auth).status_code == 422
    assert client.post(SUBSCRIBE, json={"keys": {"p256dh": "a", "auth": "b"}}, headers=auth).status_code == 422
    assert client.post(
        SUBSCRIBE, json={"endpoint": "", "keys": {"p256dh": "a", "auth": "b"}}, headers=auth
    ).status_code == 422


def test_signing_out_stops_the_notifications(
    client: TestClient, user_factory, db: Session
) -> None:
    """The whole reason the row is tied to a session."""
    headers, _ = user_factory()
    client.post(SUBSCRIBE, json=body(), headers=headers)
    assert db.scalar(select(func.count()).select_from(WebPushSubscription)) == 1

    # No body: a bearer access token alone signs this device out, and an empty
    # object is neither a valid LogoutRequest nor an absent one.
    assert client.post("/api/v1/auth/logout", headers=headers).status_code in (200, 204)
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(WebPushSubscription)) == 0


# --- Sending ---------------------------------------------------------------


def test_nothing_is_sent_without_keys(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A deployment with no VAPID pair simply does not notify, rather than
    failing somewhere in the background where nobody is looking.

    The environment is cleared explicitly: a developer with keys in their .env
    would otherwise see this pass for the wrong reason, or fail for one.
    """
    # Patched on the module rather than through the environment: get_settings
    # is process-wide and lru_cached, and clearing that cache made every test
    # after this one read a different database.
    unconfigured = Settings(
        postgres_password="x", jwt_secret_key="y" * 40,
        vapid_public_key="", vapid_private_key="",
    )
    monkeypatch.setattr(web_push, "get_settings", lambda: unconfigured)

    assert web_push.configured() is False
    sent = web_push.send_to_user(db, uuid.uuid4(), web_push.duel_challenge("Kiran"))
    assert sent == 0


def test_the_keys_have_to_come_in_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Half-configured push is worse than none: the client is offered a button
    that can never work, and the send fails on a background job."""
    # Both halves are passed explicitly every time, so a key in the developer's
    # own environment cannot quietly complete the pair and hide the failure.
    for key in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY"):
        monkeypatch.delenv(key, raising=False)
    base = {"postgres_password": "x", "jwt_secret_key": "y" * 40}

    with pytest.raises(ValueError, match="together"):
        Settings(**base, vapid_public_key="public-only", vapid_private_key="")
    with pytest.raises(ValueError, match="together"):
        Settings(**base, vapid_public_key="", vapid_private_key="private-only")
    # Both set is fine, and so is neither - the latter means "no push here".
    assert Settings(**base, vapid_public_key="a", vapid_private_key="b").vapid_public_key == "a"
    assert Settings(**base).vapid_public_key == ""


def test_every_notification_says_where_it_leads() -> None:
    """The launch checklist's rule is party events only, never a nag - so the
    reasons are named here rather than composed by a caller."""
    for notification in (
        web_push.party_quest_completed("Kiran", "Group run"),
        web_push.duel_challenge("Meera"),
        web_push.duel_resolved(won=True, who="Meera"),
        web_push.duel_resolved(won=False, who="Meera"),
    ):
        assert notification.title and notification.body
        assert notification.path.startswith("/")
