from fastapi.testclient import TestClient

from app.main import create_app


def test_liveness_and_correlation() -> None:
    with TestClient(create_app(), base_url="http://localhost") as client:
        response = client.get("/api/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.headers["X-Correlation-ID"]


def test_readiness_healthy() -> None:
    app = create_app()
    app.state.checks = {"postgresql": lambda: True, "redis": lambda: True, "schema": lambda: True}
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/health/ready").status_code == 200


def test_readiness_failure_redacts_secrets() -> None:
    def fail() -> None:
        raise RuntimeError("secret-password")

    app = create_app()
    app.state.checks = {"postgresql": fail, "redis": lambda: False}
    with TestClient(app, base_url="http://localhost") as client:
        response = client.get("/api/health/ready")
        assert response.status_code == 503
        assert "secret-password" not in response.text
        assert response.json()["dependencies"]["redis"] == "unavailable"
