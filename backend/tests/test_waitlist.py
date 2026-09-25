"""The waitlist: the only public write besides signup, so it gets the same care."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.waitlist import WaitlistEntry

WAITLIST = "/api/v1/waitlist"


def test_anyone_can_join(client: TestClient, db: Session) -> None:
    r = client.post(WAITLIST, json={"email": "lifter@example.com", "source": "hero"})
    assert r.status_code == 200, r.text
    assert r.json()["joined"] is True

    row = db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == "lifter@example.com"))
    assert row is not None and row.source == "hero"


def test_joining_twice_says_the_same_thing(client: TestClient, db: Session) -> None:
    """A different answer the second time would turn this into a way to test
    whether an address has signed up."""
    first = client.post(WAITLIST, json={"email": "twice@example.com"})
    second = client.post(WAITLIST, json={"email": "TWICE@example.com"})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()

    copies = db.scalar(
        select(func.count()).select_from(WaitlistEntry).where(WaitlistEntry.email == "twice@example.com")
    )
    assert copies == 1


def test_the_address_is_stored_lower_cased(client: TestClient, db: Session) -> None:
    client.post(WAITLIST, json={"email": "Shouty@Example.COM"})
    assert db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == "shouty@example.com")) is not None


def test_a_bad_address_is_refused(client: TestClient) -> None:
    assert client.post(WAITLIST, json={"email": "not-an-address"}).status_code == 422


def test_the_source_note_is_optional(client: TestClient, db: Session) -> None:
    assert client.post(WAITLIST, json={"email": "plain@example.com"}).status_code == 200
    row = db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == "plain@example.com"))
    assert row is not None and row.source is None


def test_an_over_long_source_is_refused(client: TestClient) -> None:
    r = client.post(WAITLIST, json={"email": "long@example.com", "source": "x" * 41})
    assert r.status_code == 422, r.text


def test_the_waitlist_is_not_an_account(client: TestClient) -> None:
    """Joining must not create anything that can be signed in to."""
    client.post(WAITLIST, json={"email": "notauser@example.com"})
    r = client.post("/api/v1/auth/login", json={"email": "notauser@example.com", "password": "anything"})
    assert r.status_code == 401, r.text
