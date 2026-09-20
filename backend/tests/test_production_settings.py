"""Production mode hides the API map (app.main.DOCS_ENABLED)."""

import importlib

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.config import get_settings

settings = get_settings()


def test_development_serves_the_api_docs(client: TestClient) -> None:
    assert client.get("/openapi.json").status_code == 200


def test_production_hides_the_api_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    # The FastAPI app reads the setting at import, so build a production app
    # by re-executing the module, then restore the development one.
    monkeypatch.setattr(settings, "environment", "production")
    production = importlib.reload(main_module)
    try:
        with TestClient(production.app) as prod_client:
            assert prod_client.get("/docs").status_code == 404
            assert prod_client.get("/redoc").status_code == 404
            assert prod_client.get("/openapi.json").status_code == 404
            assert prod_client.get("/").json()["docs"] == "disabled"
    finally:
        monkeypatch.undo()
        importlib.reload(main_module)


def _settings(**overrides):
    """A Settings built from an explicit environment, bypassing the cache."""
    from app.core.config import Settings

    base = {
        "postgres_user": "u",
        "postgres_password": "p",
        "postgres_db": "d",
        "jwt_secret_key": "x" * 48,
    }
    return Settings(**{**base, **overrides})


def test_production_refuses_the_placeholder_secret() -> None:
    # Shipped in deploy/.env.production.example: deployed unchanged, anyone
    # could mint a token for any account.
    with pytest.raises(ValueError, match="placeholder"):
        _settings(
            environment="production",
            jwt_secret_key="CHANGE_ME_GENERATE_A_RANDOM_48_BYTE_SECRET",
        )


def test_production_refuses_a_short_secret() -> None:
    with pytest.raises(ValueError, match="at least 32 bytes"):
        _settings(environment="production", jwt_secret_key="short-secret")


def test_production_accepts_a_real_secret() -> None:
    assert _settings(environment="production").environment == "production"


def test_development_is_left_alone() -> None:
    # A local stack running the example file must still start.
    assert _settings(jwt_secret_key="CHANGE_ME_GENERATE_A_RANDOM_48_BYTE_SECRET")
