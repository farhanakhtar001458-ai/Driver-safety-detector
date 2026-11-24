#!/usr/bin/env python3
"""End-to-end API smoke test for SafeWay AI.

Runs against a *running* backend and exercises the read surface plus a small set
of write paths, asserting status codes and basic payload shapes. It never
modifies production data when pointed at a demo database, but it does create
rows (a vehicle, an incident, a report) - use a disposable database.

Usage:
    .venv/bin/python scripts/smoke_api.py --base-url http://127.0.0.1:8000
    .venv/bin/python scripts/smoke_api.py --base-url http://127.0.0.1:8000 --skip-writes

Credentials default to the demo seed. Override with --email / --password.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


class Client:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.failures: list[str] = []
        self.checks = 0

    def request(self, method: str, path: str, body: Any = None, expect: int | tuple[int, ...] = 200, auth: bool = True):
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        self.checks += 1
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                status = response.status
                content_type = response.headers.get("Content-Type", "")
                if "json" not in content_type:
                    parsed = {"_binary_bytes": len(payload), "_content_type": content_type}
                else:
                    parsed = json.loads(payload) if payload else None
        except urllib.error.HTTPError as error:
            payload = error.read()
            status = error.code
            try:
                parsed = json.loads(payload) if payload else None
            except json.JSONDecodeError:
                parsed = payload.decode(errors="replace")
        except Exception as error:  # noqa: BLE001 - surface transport failures
            self.failures.append(f"{method} {path} -> transport error: {error}")
            return None

        expected = expect if isinstance(expect, tuple) else (expect,)
        if status not in expected:
            detail = parsed.get("detail") if isinstance(parsed, dict) else parsed
            self.failures.append(f"{method} {path} -> {status} (expected {expected}) {str(detail)[:160]}")
        return parsed

    def get(self, path: str, expect: int | tuple[int, ...] = 200):
        return self.request("GET", path, expect=expect)

    def post(
        self,
        path: str,
        body: Any = None,
        expect: int | tuple[int, ...] = 200,
        auth: bool = True,
    ):
        return self.request("POST", path, body or {}, expect=expect, auth=auth)

    def patch(self, path: str, body: Any = None, expect: int | tuple[int, ...] = 200):
        return self.request("PATCH", path, body or {}, expect=expect)

    def delete(self, path: str, expect: int | tuple[int, ...] = 200):
        return self.request("DELETE", path, expect=expect)


def check(condition: bool, message: str, client: Client) -> None:
    if not condition:
        client.failures.append(f"assertion failed: {message}")


def login(client: Client, email: str, password: str) -> None:
    payload = client.post(
        "/api/v1/auth/login",
        {"email": email, "password": password},
        expect=200,
        auth=False,
    )
    check(isinstance(payload, dict) and payload.get("access_token"), "login returns an access token", client)
    if isinstance(payload, dict):
        client.token = payload["access_token"]


def read_surface(client: Client) -> None:
    endpoints = [
        "/api/v1/health",
        "/api/v1/auth/me",
        "/api/v1/dashboard",
        "/api/v1/dashboard/activity",
        "/api/v1/vehicles",
        "/api/v1/vehicles/meta/status-counts",
        "/api/v1/drivers",
        "/api/v1/drivers/meta/licences-expiring",
        "/api/v1/gps/live",
        "/api/v1/gps/geofences",
        "/api/v1/gps/trails?minutes=60",
        "/api/v1/behaviour/summary?days=30",
        "/api/v1/behaviour/patterns?days=30",
        "/api/v1/behaviour/config",
        "/api/v1/behaviour/events?page_size=5",
        "/api/v1/risk/overview",
        "/api/v1/risk/model-info",
        "/api/v1/risk/assessments?page_size=5",
        "/api/v1/incidents",
        "/api/v1/incidents/summary",
        "/api/v1/maintenance/health",
        "/api/v1/maintenance/alerts",
        "/api/v1/maintenance/records",
        "/api/v1/maintenance/schedule",
        "/api/v1/reports/types",
        "/api/v1/reports/summary?report_type=weekly_safety",
        "/api/v1/notifications?page_size=5",
        "/api/v1/notifications/unread-count",
        "/api/v1/notifications/stats",
        "/api/v1/notifications/preferences",
        "/api/v1/assistant/capabilities",
        "/api/v1/subscriptions/plans",
        "/api/v1/subscriptions/me",
        "/api/v1/subscriptions/me/usage",
        "/api/v1/subscriptions/payments",
        "/api/v1/organisations/me",
        "/api/v1/organisations/me/team",
        "/api/v1/organisations/me/usage",
        "/api/v1/audit-logs?page_size=5",
        "/api/v1/ai-models",
        "/api/v1/intelligence/overview",
        "/api/v1/intelligence/hotspots",
        "/api/v1/intelligence/hazards",
        "/api/v1/intelligence/weather",
        "/api/v1/scores/leaderboard",
        "/api/v1/scores/config",
    ]
    for path in endpoints:
        client.get(path)


def write_surface(client: Client) -> None:
    stamp = int(time.time())
    vehicle = client.post(
        "/api/v1/vehicles",
        {
            "registration_number": f"SM{stamp % 10000}KE{stamp % 100:02d}",
            "vehicle_type": "van",
            "manufacturer": "Smoke",
            "model": "Test",
            "manufacturing_year": 2024,
            "fuel_type": "diesel",
            "mileage_km": 1000,
        },
        expect=(200, 201),
    )
    vehicle_id = vehicle.get("id") if isinstance(vehicle, dict) else None
    check(vehicle_id is not None, "vehicle create returns an id", client)

    driver = client.post(
        "/api/v1/drivers",
        {
            "first_name": "Smoke",
            "last_name": "Tester",
            "email": f"smoke.{stamp}@example.com",
            "status": "active",
            "years_experience": 4,
        },
        expect=(200, 201),
    )
    driver_id = driver.get("id") if isinstance(driver, dict) else None
    check(driver_id is not None, "driver create returns an id", client)

    incident = client.post(
        "/api/v1/incidents",
        {
            "title": f"Smoke test incident {stamp}",
            "incident_type": "near_miss",
            "severity": "minor",
            "description": "Created by scripts/smoke_api.py",
        },
        expect=(200, 201),
    )
    incident_id = incident.get("id") if isinstance(incident, dict) else None
    check(incident_id is not None, "incident create returns an id", client)

    if incident_id:
        client.post(f"/api/v1/incidents/{incident_id}/investigate", {"notes": "Smoke investigation"})
        client.post(f"/api/v1/incidents/{incident_id}/verify", {"notes": "Smoke verification"})
        client.post(f"/api/v1/incidents/{incident_id}/resolve", {"notes": "Smoke resolution"})
        # Repeating the same transition is idempotent (200), but a resolved
        # incident cannot move to "verified" any more - that must be rejected.
        client.post(f"/api/v1/incidents/{incident_id}/resolve", {})
        client.post(f"/api/v1/incidents/{incident_id}/verify", {}, expect=409)

    if driver_id:
        client.post("/api/v1/risk/assess", {"driver_id": driver_id}, expect=(200, 201))
        client.post(f"/api/v1/drivers/{driver_id}/scores/recompute", {}, expect=(200, 201, 404))

    report = client.post(
        "/api/v1/reports/generate",
        {"report_type": "weekly_safety", "format": "pdf", "title": f"Smoke report {stamp}"},
        expect=(200, 201),
    )
    report_id = report.get("id") if isinstance(report, dict) else None
    check(report_id is not None, "report generate returns an id", client)
    if report_id:
        download = client.get(f"/api/v1/reports/{report_id}/download")
        check(
            isinstance(download, dict) and download.get("_binary_bytes", 0) > 0,
            "report download returns a non-empty file",
            client,
        )

    # Geofence round-trip.
    fence = client.post(
        "/api/v1/gps/geofences",
        {"name": f"Smoke fence {stamp}", "center_latitude": 23.2599, "center_longitude": 77.4126, "radius_meters": 750},
        expect=(200, 201),
    )
    fence_id = fence.get("id") if isinstance(fence, dict) else None
    if fence_id:
        client.delete(f"/api/v1/gps/geofences/{fence_id}")


def guard_rails(client: Client) -> None:
    """Negative checks: the API must reject unauthenticated and invalid input."""
    client.request("GET", "/api/v1/vehicles", expect=401, auth=False)
    client.post("/api/v1/vehicles", {"registration_number": "x"}, expect=422)
    client.post("/api/v1/risk/assess", {"driver_id": 999_999}, expect=(404, 422))
    client.post("/api/v1/reports/generate", {"report_type": "not_a_report"}, expect=422)
    client.post("/api/v1/auth/login", {"email": "nobody@example.com", "password": "wrong"}, expect=401, auth=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="SafeWay AI API smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default="admin@meridian.demo")
    parser.add_argument("--password", default="Demo@12345")
    parser.add_argument("--skip-writes", action="store_true", help="only run read endpoints")
    args = parser.parse_args()

    client = Client(args.base_url)
    print(f"SafeWay AI smoke test against {args.base_url}")

    client.get("/api/v1/health", expect=200)
    login(client, args.email, args.password)
    read_surface(client)
    if not args.skip_writes:
        write_surface(client)
    guard_rails(client)

    print(f"\n{client.checks} checks, {len(client.failures)} failure(s)")
    if client.failures:
        print("\nFailures:")
        for failure in client.failures:
            print(f"  - {failure}")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
