#!/usr/bin/env python3
"""Verify that every frontend page's data contract is satisfied by the API.

`smoke_api.py` checks status codes. This script checks the *shape* of the
responses that specific UI pages depend on, so a renamed field fails loudly
instead of rendering an empty dashboard.

It performs writes (creates a vehicle, incident, geofence, hazard, report,
team member and a plan change attempt), so run it against a disposable demo
database.

Usage:
    .venv/bin/python scripts/verify_page_contracts.py --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

FAILURES: list[str] = []
CHECKS = 0


def call(method: str, path: str, token: str | None = None, body: Any = None, base: str = ""):
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
            return response.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return error.code, raw.decode(errors="replace")


def expect(condition: bool, message: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(message)


def has(payload: Any, *keys: str, where: str = "") -> None:
    expect(isinstance(payload, dict), f"{where}: expected an object, got {type(payload).__name__}")
    if not isinstance(payload, dict):
        return
    for key in keys:
        expect(key in payload, f"{where}: missing field '{key}'")


def paginated(payload: Any, where: str, item_fields: tuple[str, ...] = ()) -> None:
    has(payload, "items", "total", "page", "page_size", "pages", where=where)
    if isinstance(payload, dict) and payload.get("items"):
        first = payload["items"][0]
        for field in item_fields:
            expect(field in first, f"{where}: first item missing '{field}'")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default="admin@meridian.demo")
    parser.add_argument("--password", default="Demo@12345")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    status, auth = call("POST", "/api/v1/auth/login", body={"email": args.email, "password": args.password}, base=base)
    expect(status == 200, f"login failed: {status}")
    token = auth.get("access_token") if isinstance(auth, dict) else None
    expect(bool(token), "login did not return an access token")
    if not token:
        print("\n".join(FAILURES))
        return 1

    def get(path: str):
        return call("GET", path, token, base=base)

    def post(path: str, body: Any = None):
        return call("POST", path, token, body or {}, base=base)

    def patch(path: str, body: Any = None):
        return call("PATCH", path, token, body or {}, base=base)

    def put(path: str, body: Any = None):
        return call("PUT", path, token, body or {}, base=base)

    # ---------------------------------------------------------------- auth
    status, me = get("/api/v1/auth/me")
    expect(status == 200, f"auth/me -> {status}")
    has(me, "user", "organisation", "subscription", "usage", where="auth/me")
    if isinstance(me, dict) and isinstance(me.get("user"), dict):
        has(me["user"], "id", "email", "full_name", "role", "permissions", where="auth/me.user")
        expect(isinstance(me["user"]["permissions"], list), "auth/me.user.permissions is not a list")

    # ----------------------------------------------------------- dashboard
    status, dashboard = get("/api/v1/dashboard?days=30")
    expect(status == 200, f"dashboard -> {status}")
    has(dashboard, "kpis", "trend", "events_by_type", "events_by_severity", "vehicle_activity",
        "leaderboard", "vehicle_health", "recent_incidents", "recent_notifications", "disclaimer",
        where="dashboard")
    kpis = (dashboard or {}).get("kpis", {})
    for key in ("total_vehicles", "total_drivers", "avg_driver_score", "maintenance_alerts",
                "open_incidents", "simulated_share_pct", "distance_period_km"):
        expect(key in kpis, f"dashboard.kpis missing '{key}'")
    expect(bool((dashboard or {}).get("disclaimer")), "dashboard.disclaimer is empty")
    if (dashboard or {}).get("vehicle_health"):
        has(dashboard["vehicle_health"][0], "vehicle_id", "registration_number", "health_score",
            "fault_codes", "is_simulated", where="dashboard.vehicle_health[0]")

    # ------------------------------------------------------------ tracking
    status, live = get("/api/v1/gps/live")
    expect(status == 200, f"gps/live -> {status}")
    expect(isinstance(live, list), "gps/live is not a list")
    if live:
        has(live[0], "vehicle_id", "registration_number", "latitude", "longitude", "speed_kph",
            "status", "is_simulated", where="gps/live[0]")
    status, trails = get("/api/v1/gps/trails?minutes=180")
    expect(status == 200, f"gps/trails -> {status}")
    if trails:
        has(trails[0], "vehicle_id", "registration_number", "points", "is_simulated", where="gps/trails[0]")
    status, fences = get("/api/v1/gps/geofences")
    expect(status == 200, f"gps/geofences -> {status}")
    if fences:
        has(fences[0], "id", "name", "center_latitude", "center_longitude", "radius_meters", "is_active",
            where="gps/geofences[0]")

    # ------------------------------------------------------------ vehicles
    status, vehicles = get("/api/v1/vehicles?page_size=5")
    paginated(vehicles, "vehicles", ("id", "registration_number", "status", "mileage_km", "vehicle_type"))
    vehicle_id = vehicles["items"][0]["id"] if isinstance(vehicles, dict) and vehicles.get("items") else 1
    status, overview = get(f"/api/v1/vehicles/{vehicle_id}/overview")
    expect(status == 200, f"vehicles/{vehicle_id}/overview -> {status}")
    has(overview, "vehicle", "health", "last_location", "open_alerts", "recent_events", "trips_count",
        where="vehicle overview")
    if isinstance(overview, dict) and isinstance(overview.get("health"), dict):
        has(overview["health"], "health_score", "is_simulated", "fault_codes", where="vehicle overview.health")

    # ------------------------------------------------------------- drivers
    status, drivers = get("/api/v1/drivers?page_size=5")
    paginated(drivers, "drivers", ("id", "full_name", "status", "licence_expiry", "avatar_color"))
    driver_id = drivers["items"][0]["id"] if isinstance(drivers, dict) and drivers.get("items") else 1
    status, scores = get(f"/api/v1/drivers/{driver_id}/scores")
    expect(status == 200, f"drivers/{driver_id}/scores -> {status}")
    has(scores, "history", "latest", "recommendations", "data_coverage", "disclaimer", where="driver scores")
    if isinstance(scores, dict) and scores.get("history"):
        has(scores["history"][0], "period_start", "overall_score", where="driver scores.history[0]")
    if isinstance(scores, dict) and scores.get("latest"):
        has(scores["latest"], "overall_score", "speed_score", "braking_score", "confidence",
            "model_version", where="driver scores.latest")
    status, coaching = post(f"/api/v1/drivers/{driver_id}/coaching-report")
    expect(status == 200, f"coaching-report -> {status}")
    has(coaching, "summary", "strengths", "recommendations", "disclaimer", where="coaching report")

    # ----------------------------------------------------------- behaviour
    status, summary = get("/api/v1/behaviour/summary?days=30")
    expect(status == 200, f"behaviour/summary -> {status}")
    has(summary, "total_events", "high_risk_events", "by_type", "by_severity", "trend", "top_drivers",
        "safest_drivers", "simulation_share_pct", where="behaviour/summary")
    status, patterns = get("/api/v1/behaviour/patterns?days=30")
    expect(status == 200, f"behaviour/patterns -> {status}")
    has(patterns, "patterns", "methodology", "limitations", where="behaviour/patterns")
    status, config = get("/api/v1/behaviour/config")
    expect(status == 200, f"behaviour/config -> {status}")
    has(config, "thresholds", "defaults", "speed_limits", where="behaviour/config")

    # ---------------------------------------------------------------- risk
    status, overview = get("/api/v1/risk/overview")
    expect(status == 200, f"risk/overview -> {status}")
    has(overview, "total_assessed", "by_level", "high_risk_drivers", "fleet_risk_index", "model_info",
        "disclaimer", where="risk/overview")
    status, model = get("/api/v1/risk/model-info")
    expect(status == 200, f"risk/model-info -> {status}")
    has(model, "name", "version", "metrics", "feature_importance", "features", "limitations", "disclaimer",
        where="risk/model-info")
    expect(isinstance(model.get("feature_importance"), dict),
           "risk/model-info.feature_importance should be a mapping")
    status, assessed = post("/api/v1/risk/assess", {"driver_id": driver_id})
    expect(status in (200, 201), f"risk/assess -> {status}")
    has(assessed, "risk_level", "risk_score", "indicators", "explanation", "recommendations", "confidence",
        "inputs", "limitations", "model_version", where="risk/assess")

    # ------------------------------------------------------------ incidents
    status, incidents = get("/api/v1/incidents?page_size=5")
    paginated(incidents, "incidents", ("id", "title", "severity", "status", "occurred_at", "evidence"))
    status, inc_summary = get("/api/v1/incidents/summary")
    expect(status == 200, f"incidents/summary -> {status}")
    has(inc_summary, "total", "open", "under_investigation", "resolved", "false_alerts", "by_type",
        "by_severity", "response_time_hours_avg", where="incidents/summary")
    if isinstance(incidents, dict) and incidents.get("items"):
        incident_id = incidents["items"][0]["id"]
        status, detail = get(f"/api/v1/incidents/{incident_id}")
        expect(status == 200, f"incidents/{incident_id} -> {status}")
        has(detail, "investigation_notes", "resolution_notes", "reporter_name", "verified_at", "resolved_at",
            where="incident detail")

    # --------------------------------------------------------- maintenance
    status, health = get("/api/v1/maintenance/health")
    expect(status == 200, f"maintenance/health -> {status}")
    if health:
        has(health[0], "vehicle_id", "registration_number", "health_score", "engine_temperature_c",
            "fuel_level_pct", "fault_codes", "is_simulated", where="maintenance/health[0]")
    status, schedule = get("/api/v1/maintenance/schedule")
    expect(status == 200, f"maintenance/schedule -> {status}")
    if schedule:
        has(schedule[0], "vehicle_id", "next_service_km", "urgency", "open_alerts", where="maintenance/schedule[0]")
    status, records = get("/api/v1/maintenance/records?page_size=5")
    paginated(records, "maintenance/records", ("id", "title", "record_type", "odometer_km", "cost", "performed_at"))
    status, prediction = post(f"/api/v1/maintenance/predict/{vehicle_id}")
    expect(status == 200, f"maintenance/predict -> {status}")
    has(prediction, "failure_probability", "risk_level", "components", "recommendation", "data_sources",
        "is_simulated", "disclaimer", where="maintenance/predict")
    if isinstance(prediction, dict) and prediction.get("components"):
        has(prediction["components"][0], "component", "probability", "basis",
            where="maintenance/predict.components[0]")

    # ------------------------------------------------------------- reports
    status, types = get("/api/v1/reports/types")
    expect(status == 200, f"reports/types -> {status}")
    has(types, "types", "formats", where="reports/types")
    status, report_summary = get("/api/v1/reports/summary?report_type=weekly_safety")
    expect(status == 200, f"reports/summary -> {status}")
    has(report_summary, "kpis", "charts", "period", "disclaimer", where="reports/summary")
    status, generated = post("/api/v1/reports/generate", {"report_type": "weekly_safety", "format": "pdf"})
    expect(status in (200, 201), f"reports/generate -> {status}")
    has(generated, "id", "report_type", "format", "status", "row_count", "created_at", where="reports/generate")

    # -------------------------------------------------------- notifications
    status, notifications = get("/api/v1/notifications?page_size=5")
    paginated(notifications, "notifications", ("id", "title", "message", "priority", "is_read", "created_at"))
    status, prefs = get("/api/v1/notifications/preferences")
    expect(status == 200, f"notifications/preferences -> {status}")
    has(prefs, "in_app", "email", "sms", "critical_only", "quiet_hours_start", "quiet_hours_end",
        where="notifications/preferences")
    status, stats = get("/api/v1/notifications/stats")
    expect(status == 200, f"notifications/stats -> {status}")
    has(stats, "total", "by_type", "by_priority", where="notifications/stats")

    # ----------------------------------------------------------- assistant
    status, capabilities = get("/api/v1/assistant/capabilities")
    expect(status == 200, f"assistant/capabilities -> {status}")
    has(capabilities, "mode", "can_answer_about", "will_not_do", "disclaimer", where="assistant/capabilities")
    status, chat = post("/api/v1/assistant/chat", {"message": "Summarise my fleet's recent events.", "include_fleet_context": True})
    expect(status == 200, f"assistant/chat -> {status}")
    has(chat, "reply", "mode", "suggestions", "grounding", "disclaimer", where="assistant/chat")

    # ---------------------------------------------------- road safety intel
    status, intel = get("/api/v1/intelligence/overview")
    expect(status == 200, f"intelligence/overview -> {status}")
    has(intel, "active_hazards", "hotspots", "high_severity_hazards", "disclaimer", where="intelligence/overview")
    status, hotspots = get("/api/v1/intelligence/hotspots")
    expect(status == 200, f"intelligence/hotspots -> {status}")
    has(hotspots, "hotspots", where="intelligence/hotspots")
    if isinstance(hotspots, dict) and hotspots.get("hotspots"):
        has(hotspots["hotspots"][0], "latitude", "longitude", "label", "severity", "is_illustrative",
            where="hotspots[0]")
    status, hazards = get("/api/v1/intelligence/hazards")
    expect(status == 200, f"intelligence/hazards -> {status}")
    status, weather = get("/api/v1/intelligence/weather")
    expect(status == 200, f"intelligence/weather -> {status}")
    has(weather, "simulated", "source", "condition", "observed_at", where="intelligence/weather")
    status, route = post("/api/v1/intelligence/route-analysis",
                         {"points": [{"latitude": 23.2599, "longitude": 77.4126},
                                     {"latitude": 23.2330, "longitude": 77.4100}]})
    expect(status == 200, f"intelligence/route-analysis -> {status}")
    has(route, "distance_km", "risk_rating", "risk_score", "hazard_count", "warnings", "recommendations",
        "disclaimer", where="route-analysis")
    status, hazard = post("/api/v1/intelligence/hazards", {
        "latitude": 23.2599, "longitude": 77.4126, "hazard_type": "pothole",
        "severity": "low", "description": "Contract verification", "expires_in_hours": 1,
    })
    expect(status in (200, 201), f"intelligence/hazards POST -> {status}")

    # ------------------------------------------------------ settings/team
    status, org = get("/api/v1/organisations/me")
    expect(status == 200, f"organisations/me -> {status}")
    has(org, "id", "name", "slug", "timezone", "monitoring_policy_accepted_at", where="organisations/me")
    status, team = get("/api/v1/organisations/me/team")
    paginated(team, "team", ("id", "email", "full_name", "role", "is_active"))
    status, audit = get("/api/v1/audit-logs?page_size=5")
    paginated(audit, "audit-logs", ("id", "action", "created_at"))

    # ------------------------------------------------------------- billing
    status, plans = get("/api/v1/subscriptions/plans")
    expect(status == 200, f"subscriptions/plans -> {status}")
    expect(isinstance(plans, list) and len(plans) >= 4, "expected at least four plans")
    for plan in plans or []:
        has(plan, "code", "name", "price_monthly", "max_vehicles", "max_drivers", "features", "trial_days",
            "is_custom", where=f"plan {plan.get('code')}")
    status, subscription = get("/api/v1/subscriptions/me")
    expect(status == 200, f"subscriptions/me -> {status}")
    has(subscription, "status", "seats", "plan", "current_period_end", "cancel_at_period_end",
        where="subscriptions/me")
    status, payments = get("/api/v1/subscriptions/payments")
    expect(status == 200, f"subscriptions/payments -> {status}")
    expect(isinstance(payments, list), "subscriptions/payments is not a list")

    print(f"\n{CHECKS} contract checks, {len(FAILURES)} failure(s)")
    if FAILURES:
        print("\nFailures:")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print("All page contracts satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
