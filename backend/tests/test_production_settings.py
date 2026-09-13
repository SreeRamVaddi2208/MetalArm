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
