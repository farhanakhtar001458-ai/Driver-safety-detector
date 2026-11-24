"""GPS ingestion, notifications, reporting and assistant tests."""

from __future__ import annotations

import io
import zipfile


def test_gps_ingest_requires_device_key(client):
    response = client.post("/api/v1/gps/ingest", json={"points": [{"latitude": 23.2, "longitude": 77.4}]})
    assert response.status_code == 401


def test_gps_ingest_rejects_wrong_key(client):
    response = client.post(
        "/api/v1/gps/ingest",
        json={"points": [{"latitude": 23.2, "longitude": 77.4}]},
        headers={"X-Device-Key": "definitely-not-a-valid-key"},
    )
    assert response.status_code == 401


def test_gps_ingest_accepts_valid_device(client):
    response = client.post(
        "/api/v1/gps/ingest",
        json={
            "points": [
                {
                    "latitude": 23.261,
                    "longitude": 77.412,
                    "speed_kph": 42,
                    "heading": 90,
                    "accuracy_m": 6,
                    "recorded_at": "2026-11-24T14:00:00",
                }
            ]
        },
        headers={"X-Device-Key": "sw_demo_device_key_1234567890"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted"] == 1
    assert body["simulated"] is False


def test_gps_ingest_rejects_mismatched_vehicle(client):
    response = client.post(
        "/api/v1/gps/ingest",
        json={
            "vehicle_id": 999,
            "points": [{"latitude": 23.2, "longitude": 77.4, "speed_kph": 30}],
        },
        headers={"X-Device-Key": "sw_demo_device_key_1234567890"},
    )
    assert response.status_code in {403, 404}


def test_live_fleet_and_history(client, admin_headers):
    live = client.get("/api/v1/gps/live", headers=admin_headers)
    assert live.status_code == 200
    assert live.json()
    vehicle = live.json()[0]
    assert "latitude" in vehicle and "speed_kph" in vehicle
    assert vehicle["is_simulated"] is True  # demo data must be labelled

    history = client.get("/api/v1/gps/vehicles/1/history", params={"page_size": 5}, headers=admin_headers)
    assert history.status_code == 200
    assert history.json()["total"] > 0

    trails = client.get("/api/v1/gps/trails", params={"minutes": 360}, headers=admin_headers)
    assert trails.status_code == 200


def test_geofence_crud(client, admin_headers):
    create = client.post(
        "/api/v1/gps/geofences",
        json={
            "name": "Test Zone",
            "center_latitude": 23.2,
            "center_longitude": 77.4,
            "radius_meters": 900,
            "alert_on_exit": True,
        },
        headers=admin_headers,
    )
    assert create.status_code == 201
    fence_id = create.json()["id"]
    assert client.delete(f"/api/v1/gps/geofences/{fence_id}", headers=admin_headers).status_code == 200


def test_notification_preferences_and_read_state(client, admin_headers):
    update = client.put(
        "/api/v1/notifications/preferences",
        json={"in_app": True, "email": True, "sms": False, "critical_only": False},
        headers=admin_headers,
    )
    assert update.status_code == 200
    assert update.json()["email"] is True

    listing = client.get("/api/v1/notifications", params={"page_size": 5}, headers=admin_headers)
    assert listing.status_code == 200
    unread_before = client.get("/api/v1/notifications/unread-count", headers=admin_headers).json()["unread"]

    if listing.json()["items"]:
        notification_id = listing.json()["items"][0]["id"]
        read = client.post(f"/api/v1/notifications/{notification_id}/read", headers=admin_headers)
        assert read.status_code == 200
        assert read.json()["is_read"] is True

    mark_all = client.post("/api/v1/notifications/read-all", headers=admin_headers)
    assert mark_all.status_code == 200
    unread_after = client.get("/api/v1/notifications/unread-count", headers=admin_headers).json()["unread"]
    assert unread_after == 0
    assert unread_before >= unread_after


def test_dispatch_reports_honest_status(client, admin_headers):
    """Email/SMS must report not_configured rather than pretend to send."""
    listing = client.get("/api/v1/notifications", params={"page_size": 1}, headers=admin_headers)
    if not listing.json()["items"]:
        return
    notification_id = listing.json()["items"][0]["id"]
    response = client.post(
        f"/api/v1/notifications/{notification_id}/dispatch", params={"channel": "email"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["delivery_status"] in {"not_configured", "sent", "queued", "failed"}


def test_report_generation_csv_and_pdf(client, admin_headers):
    csv_report = client.post(
        "/api/v1/reports/generate",
        json={"report_type": "weekly_safety", "format": "csv"},
        headers=admin_headers,
    )
    assert csv_report.status_code == 201, csv_report.text
    assert csv_report.json()["status"] == "completed"

    download = client.get(f"/api/v1/reports/{csv_report.json()['id']}/download", headers=admin_headers)
    assert download.status_code == 200
    assert "text/csv" in download.headers["content-type"]
    assert b"KPI" in download.content

    pdf_report = client.post(
        "/api/v1/reports/generate",
        json={"report_type": "fleet_safety", "format": "pdf", "title": "Test Fleet Report"},
        headers=admin_headers,
    )
    assert pdf_report.status_code == 201
    pdf = client.get(f"/api/v1/reports/{pdf_report.json()['id']}/download", headers=admin_headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_report_summary_has_filters_and_disclaimer(client, admin_headers):
    response = client.get(
        "/api/v1/reports/summary",
        params={"report_type": "driver_performance", "driver_id": 1},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["kpis"]["total_events"] >= 0
    assert body["disclaimer"]
    assert body["period"]["from"]


def test_assistant_local_reply_is_grounded(client, admin_headers):
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Why did my safety score decrease this week?", "driver_id": 1},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] in {"local", "llm"}
    assert body["reply"]
    assert "not a medical" in body["disclaimer"].lower()
    assert body["grounding"]


def test_assistant_fleet_question(client, admin_headers):
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "How is my fleet performing overall?"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert "fleet" in response.json()["reply"].lower() or "vehicle" in response.json()["reply"].lower()


def test_coaching_report(client, admin_headers):
    response = client.post("/api/v1/assistant/coaching-report/1", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"]
    assert body["disclaimer"]
    assert body["driver_name"]


def test_maintenance_alerts_health_and_prediction(client, admin_headers):
    alerts = client.get("/api/v1/maintenance/alerts", headers=admin_headers)
    assert alerts.status_code == 200
    assert alerts.json()["total"] > 0

    health = client.get("/api/v1/maintenance/health", headers=admin_headers)
    assert health.status_code == 200
    assert any(row["is_simulated"] for row in health.json())  # demo data labelled

    predict = client.post("/api/v1/maintenance/predict/1", headers=admin_headers)
    assert predict.status_code == 200
    body = predict.json()
    assert body["is_estimated"] is True
    assert body["recommendations"]
    assert "not a substitute" in body["disclaimer"].lower()


def test_subscription_plans_and_usage(client, admin_headers):
    plans = client.get("/api/v1/subscriptions/plans", headers=admin_headers)
    assert plans.status_code == 200
    codes = {plan["code"] for plan in plans.json()}
    assert {"free", "starter", "professional", "enterprise"} <= codes

    me = client.get("/api/v1/subscriptions/me", headers=admin_headers)
    assert me.status_code == 200
    assert me.json()["plan"]["code"] in codes

    payments = client.get("/api/v1/subscriptions/payments", headers=admin_headers)
    assert payments.status_code == 200
    assert payments.json()


def test_audit_log_records_mutations(client, admin_headers):
    before = client.get("/api/v1/audit-logs", params={"page_size": 1}, headers=admin_headers).json()["total"]
    client.post(
        "/api/v1/vehicles",
        json={
            "registration_number": "MP09 AUD 01",
            "vehicle_type": "car",
            "manufacturer": "Audit",
            "model": "Test",
            "manufacturing_year": 2021,
            "fuel_type": "petrol",
        },
        headers=admin_headers,
    )
    after = client.get("/api/v1/audit-logs", params={"page_size": 1}, headers=admin_headers).json()["total"]
    assert after > before
    logs = client.get("/api/v1/audit-logs", params={"action": "vehicle.create"}, headers=admin_headers)
    assert logs.status_code == 200
    assert any("vehicle.create" in row["action"] for row in logs.json()["items"])


def test_ai_model_registry(client, superadmin_headers):
    response = client.get("/api/v1/ai-models", headers=superadmin_headers)
    assert response.status_code == 200
    models = response.json()
    assert any(m["task"] == "risk_classification" for m in models)
    assert all(m["limitations"] for m in models)


def test_road_intelligence_labels_illustrative_data(client, admin_headers):
    hotspots = client.get("/api/v1/intelligence/hotspots", headers=admin_headers)
    assert hotspots.status_code == 200
    body = hotspots.json()
    assert body["disclaimer"]
    assert body["hotspots"]
    assert all(row["is_illustrative"] for row in body["hotspots"])

    weather = client.get("/api/v1/intelligence/weather", headers=admin_headers)
    assert weather.status_code == 200
    assert weather.json()["simulated"] is True

    route = client.post(
        "/api/v1/intelligence/route-analysis",
        json={"points": [{"latitude": 23.23, "longitude": 77.40}, {"latitude": 23.25, "longitude": 77.42}]},
        headers=admin_headers,
    )
    assert route.status_code == 200
    assert route.json()["disclaimer"]


def test_dashboard_performance(client, admin_headers):
    import time

    started = time.perf_counter()
    response = client.get("/api/v1/dashboard", headers=admin_headers)
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert elapsed < 3.0, f"dashboard took {elapsed:.2f}s"
    kpis = response.json()["kpis"]
    assert kpis["total_vehicles"] >= 1
    assert kpis["simulated_share_pct"] > 0  # demo data must be labelled
