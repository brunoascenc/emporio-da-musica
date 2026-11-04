from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.core.config import Settings
from src.core.database import get_database_engine
from src.main import create_app


@pytest.fixture
def health_client(monkeypatch):
    engine = MagicMock()
    monkeypatch.setattr("src.main.create_database_engine", lambda settings: engine)
    app = create_app(Settings(_env_file=None, postgres_password="test-password"))
    app.dependency_overrides[get_database_engine] = lambda: engine
    with TestClient(app) as client:
        yield client, engine
    engine.dispose.assert_called_once()


def test_healthy_database_with_pgvector(health_client):
    client, engine = health_client
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one_or_none.return_value = "0.8.0"
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "up", "pgvector": True}


def test_missing_pgvector_returns_service_unavailable(health_client):
    client, engine = health_client
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one_or_none.return_value = None
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "up", "pgvector": False}


def test_database_failure_does_not_expose_connection_details(health_client, caplog):
    client, engine = health_client
    engine.connect.side_effect = OperationalError("private-connection-details", {}, Exception("secret"))
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "down", "pgvector": False}
    assert "private-connection-details" not in response.text + caplog.text
    assert "secret" not in response.text + caplog.text
