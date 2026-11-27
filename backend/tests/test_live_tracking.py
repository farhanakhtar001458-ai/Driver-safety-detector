"""Regression coverage for tracking streams and tenant isolation."""

from app.models import Vehicle
from app.services.simulator import TelemetrySimulator
from app.services.ws_hub import manager


def test_websocket_disconnect_cleans_up_room_and_user(client):
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@meridian.demo", "password": "Demo@12345"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    user_id = response.json()["user"]["id"]
    org_id = response.json()["user"]["organisation_id"]
    before_room = len(manager.rooms.get(org_id, set()))
    before_user = len(manager.user_sockets.get(user_id, set()))
    with client.websocket_connect(f"/api/v1/ws/fleet?token={token}") as socket:
        assert socket.receive_json()["type"] == "connection"
        snapshot = socket.receive_json()
        assert snapshot["type"] == "fleet_snapshot"
        assert all("ignition_on" in vehicle for vehicle in snapshot["vehicles"])
        assert len(manager.rooms[org_id]) == before_room + 1
    assert len(manager.rooms.get(org_id, set())) == before_room
    assert len(manager.user_sockets.get(user_id, set())) == before_user


def test_simulator_publishes_only_to_own_organisation(db, monkeypatch):
    published = []
    monkeypatch.setattr(manager, "publish", lambda organisation_id, payload: published.append((organisation_id, payload)))
    simulator = TelemetrySimulator()
    result = simulator.tick()
    assert result["vehicles"]
    assert published
    for org_id, payload in published:
        assert org_id is not None
        assert payload["vehicles"]
        for row in payload["vehicles"]:
            assert db.get(Vehicle, row["vehicle_id"]).organisation_id == org_id
