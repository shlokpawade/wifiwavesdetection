from fastapi.testclient import TestClient

from app.main import app


def test_health_and_status_flow() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        connect = client.post("/api/device/connect", json={"source": "simulator"})
        assert connect.status_code == 200
        assert connect.json()["connected"] is True

        status = client.get("/api/status")
        assert status.status_code == 200
        assert status.json()["source"] == "simulator"

        disconnect = client.post("/api/device/disconnect")
        assert disconnect.status_code == 200
        assert disconnect.json()["connected"] is False
