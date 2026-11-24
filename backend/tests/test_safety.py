"""Behaviour analytics, scoring, risk and incident workflow tests."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models import DrivingEvent
from app.services.ai.risk_model import model_info, risk_level_from_score
from app.services.ai.rules_engine import DEFAULT_THRESHOLDS, detect_events
from app.services.ai.scoring import compute_score


def _event(event_type: str, severity: str = "medium", sensor: dict | None = None) -> DrivingEvent:
    return DrivingEvent(
        event_type=event_type,
        severity=severity,
        sensor_data=sensor or {},
        speed_kph=70,
        occurred_at=datetime.utcnow(),
    )


def test_rules_engine_detects_speeding_and_braking():
    now = datetime.utcnow()
    prev = {"latitude": 23.2, "longitude": 77.4, "speed_kph": 60, "heading": 90, "recorded_at": now}
    current = {"latitude": 23.2, "longitude": 77.4, "speed_kph": 80, "heading": 90, "recorded_at": now + timedelta(seconds=3)}
    events = detect_events(prev, current, DEFAULT_THRESHOLDS, speed_limit_kph=60)
    assert any(e["event_type"] == "speeding" for e in events)
    speeding = next(e for e in events if e["event_type"] == "speeding")
    assert speeding["severity"] == "high"
    assert speeding["sensor_data"]["excess_kph"] == 20.0

    braking_prev = {"latitude": 23.2, "longitude": 77.4, "speed_kph": 80, "heading": 90, "recorded_at": now}
    braking_now = {"latitude": 23.2, "longitude": 77.4, "speed_kph": 10, "heading": 90, "recorded_at": now + timedelta(seconds=3)}
    braking = detect_events(braking_prev, braking_now, DEFAULT_THRESHOLDS, speed_limit_kph=60)
    assert any(e["event_type"] == "harsh_braking" for e in braking)
    assert all("recommended_action" in e for e in braking)


def test_rules_engine_ignores_large_time_gaps():
    now = datetime.utcnow()
    prev = {"latitude": 23.2, "longitude": 77.4, "speed_kph": 10, "heading": 0, "recorded_at": now - timedelta(hours=2)}
    current = {"latitude": 23.3, "longitude": 77.5, "speed_kph": 120, "heading": 0, "recorded_at": now}
    assert detect_events(prev, current, DEFAULT_THRESHOLDS, 60) == []


def test_scoring_is_deterministic_and_bounded():
    events = [_event("speeding", "high", {"excess_kph": 25}) for _ in range(5)]
    events += [_event("harsh_braking", "medium", {"deceleration_mps2": 3.4}) for _ in range(3)]
    first = compute_score(events, 500)
    second = compute_score(events, 500)
    assert first == second
    assert 0 <= first["overall"] <= 100
    assert first["overall"] < 100
    assert first["speed"] < 100
    assert first["confidence"] >= 0.2


def test_missing_seatbelt_data_does_not_penalise():
    clean = compute_score([], 100)
    assert clean["seatbelt"] is None
    assert clean["overall"] == 100.0
    assert "seatbelt" in clean["breakdown"]["excluded_categories"]
    # Weights of present categories must renormalise to 1.
    assert abs(sum(clean["breakdown"]["weights_used"].values()) - 1.0) < 0.01


def test_zero_distance_is_handled_without_division_error():
    result = compute_score([_event("speeding", "medium")], 0)
    assert result["events_count"] == 1
    assert 0 <= result["overall"] <= 100
    assert result["confidence"] <= 0.8


def test_risk_model_metrics_are_acceptable():
    info = model_info()
    assert info["metrics"]["auc_roc"] >= 0.8, info["metrics"]
    assert info["metrics"]["brier_score"] <= 0.2
    assert "synthetic" in info["training"]["dataset"].lower()
    assert info["limitations"]


def test_risk_level_thresholds():
    assert risk_level_from_score(0.1) == "low"
    assert risk_level_from_score(0.3) == "moderate"
    assert risk_level_from_score(0.6) == "high"
    assert risk_level_from_score(0.9) == "critical"


def test_risk_assessment_endpoint(client, admin_headers):
    response = client.post("/api/v1/risk/assess", json={"driver_id": 1}, headers=admin_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["risk_level"] in {"low", "moderate", "high", "critical"}
    assert 0 <= body["risk_score"] <= 1
    assert body["indicators"]
    assert body["limitations"]
    assert "model_version" in body
    assert "not a prediction" in body["explanation"].lower()


def test_risk_model_info_endpoint(client, admin_headers):
    response = client.get("/api/v1/risk/model-info", headers=admin_headers)
    assert response.status_code == 200
    assert "feature_importance" in response.json()
    assert "disclaimer" in response.json()


def test_behaviour_events_list_and_summary(client, admin_headers):
    events = client.get("/api/v1/behaviour/events", params={"page_size": 5}, headers=admin_headers)
    assert events.status_code == 200
    assert events.json()["total"] > 0
    item = events.json()["items"][0]
    assert item["event_type"] and item["severity"]
    assert "sensor_data" in item

    summary = client.get("/api/v1/behaviour/summary", params={"days": 90}, headers=admin_headers)
    assert summary.status_code == 200
    assert summary.json()["total_events"] > 0
    assert summary.json()["by_type"]


def test_behaviour_patterns_include_limitations(client, admin_headers):
    response = client.get("/api/v1/behaviour/patterns", params={"days": 30}, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["patterns"]
    assert body["limitations"]
    assert "descriptive" in body["methodology"].lower()
    for pattern in body["patterns"]:
        assert pattern["evidence"]  # every insight is backed by evidence


def test_behaviour_config_update_and_validation(client, admin_headers):
    update = client.put("/api/v1/behaviour/config", json={"speeding_margin_kph": 7}, headers=admin_headers)
    assert update.status_code == 200
    assert update.json()["thresholds"]["speeding_margin_kph"] == 7.0

    bad = client.put("/api/v1/behaviour/config", json={"nonexistent_threshold": 5}, headers=admin_headers)
    assert bad.status_code == 422
    negative = client.put("/api/v1/behaviour/config", json={"speeding_margin_kph": -3}, headers=admin_headers)
    assert negative.status_code == 422


def test_incident_workflow(client, admin_headers):
    create = client.post(
        "/api/v1/incidents",
        json={
            "title": "Test near miss at junction",
            "description": "Automated test incident",
            "vehicle_id": 1,
            "driver_id": 1,
            "severity": "moderate",
            "incident_type": "near_miss",
        },
        headers=admin_headers,
    )
    assert create.status_code == 201
    incident_id = create.json()["id"]
    assert create.json()["status"] == "new"
    assert create.json()["emergency_contact"]["note"]

    investigate = client.post(
        f"/api/v1/incidents/{incident_id}/investigate", json={"notes": "reviewing"}, headers=admin_headers
    )
    assert investigate.status_code == 200
    assert investigate.json()["status"] == "under_investigation"

    verify = client.post(
        f"/api/v1/incidents/{incident_id}/verify", json={"notes": "confirmed by reviewer"}, headers=admin_headers
    )
    assert verify.status_code == 200
    assert verify.json()["verified_at"]

    resolve = client.post(
        f"/api/v1/incidents/{incident_id}/resolve", json={"notes": "coaching completed"}, headers=admin_headers
    )
    assert resolve.status_code == 200
    assert resolve.json()["status"] == "resolved"

    invalid = client.patch(
        f"/api/v1/incidents/{incident_id}", json={"status": "new"}, headers=admin_headers
    )
    assert invalid.status_code == 409


def test_incident_false_alert_path(client, admin_headers):
    create = client.post(
        "/api/v1/incidents",
        json={"title": "Sensor artefact", "severity": "minor", "incident_type": "other"},
        headers=admin_headers,
    ).json()
    response = client.post(
        f"/api/v1/incidents/{create['id']}/false-alert",
        json={"notes": "reviewed camera footage - no event"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "false_alert"


def test_incident_summary_counts(client, admin_headers):
    response = client.get("/api/v1/incidents/summary", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert "response_time_hours_avg" in body


def test_score_leaderboard_and_detail(client, admin_headers):
    leaderboard = client.get("/api/v1/scores/leaderboard", headers=admin_headers)
    assert leaderboard.status_code == 200
    rows = leaderboard.json()
    assert rows
    assert all(0 <= row["overall_score"] <= 100 for row in rows)
    assert "confidence" in rows[0]

    detail = client.get("/api/v1/drivers/1/scores", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["recommendations"]
    assert detail.json()["disclaimer"]
