"""/health must report readiness, not merely liveness.

Regression guard for a real bug: on a fresh volume with no `alembic upgrade
head`, /health returned 200 "ok" because SELECT 1 succeeds against an empty
database, while every real request failed with `relation "users" does not
exist`. A health check that passes on a broken deployment is worse than none.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db import schema_state


def test_health_reports_ok_on_a_migrated_database(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["dependencies"]["postgres"]["connected"] is True
    assert body["dependencies"]["redis"]["connected"] is True


def test_health_reports_the_real_server_versions(client: TestClient) -> None:
    """A pass must be distinguishable from a stubbed response."""
    deps = client.get("/health").json()["dependencies"]
    assert deps["postgres"]["server_version"]
    assert deps["redis"]["server_version"]


def test_health_includes_the_applied_migration_revision(client: TestClient) -> None:
    schema = client.get("/health").json()["dependencies"]["postgres"]["schema"]
    assert schema["ready"] is True
    assert schema["applied_revision"] == schema_state.expected_head()


def test_health_fails_when_the_database_has_never_been_migrated(
    client: TestClient,
) -> None:
    """The exact fresh-volume case: connected, but no schema."""
    with patch.object(schema_state, "applied_revision", return_value=None):
        r = client.get("/health")

    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    schema = body["dependencies"]["postgres"]["schema"]
    assert schema["ready"] is False
    # The message must name the fix, not just the symptom.
    assert "alembic upgrade head" in schema["error"]


def test_health_fails_when_the_schema_is_behind_the_code(
    client: TestClient,
) -> None:
    """Migrated, but to an older revision than this image expects."""
    with patch.object(schema_state, "applied_revision", return_value="deadbeef1234"):
        r = client.get("/health")

    assert r.status_code == 503
    schema = r.json()["dependencies"]["postgres"]["schema"]
    assert schema["ready"] is False
    assert schema["applied_revision"] == "deadbeef1234"
    assert schema["expected_revision"] == schema_state.expected_head()


def test_expected_head_is_resolvable() -> None:
    """If this returns None the check silently degrades to liveness-only."""
    assert schema_state.expected_head() is not None
