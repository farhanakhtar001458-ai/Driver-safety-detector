"""Aggregated dashboard queries.

All numbers are computed from the tenant's own rows. Simulated telemetry is
counted but clearly labelled through ``simulated_share_pct``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Driver,
    DriverScore,
    DrivingEvent,
    Incident,
    MaintenanceAlert,
    Trip,
    Vehicle,
    VehicleHealthReading,
)


def _weekly_trend(db: Session, org_id: int, weeks: int = 8) -> list[dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=7 * weeks)
    rows = (
        db.query(DrivingEvent)
        .filter(DrivingEvent.organisation_id == org_id, DrivingEvent.occurred_at >= since)
        .all()
    )
    buckets: dict[str, dict[str, Any]] = {}
    now = datetime.utcnow()
    for i in range(weeks - 1, -1, -1):
        start = now - timedelta(days=7 * (i + 1))
        label = start.strftime("%d %b")
        buckets[label] = {"label": label, "events": 0, "high_risk": 0, "simulated": 0}
    for event in rows:
        weeks_ago = int((now - event.occurred_at).days // 7)
        if 0 <= weeks_ago < weeks:
            label = (now - timedelta(days=7 * (weeks_ago + 1))).strftime("%d %b")
            if label in buckets:
                buckets[label]["events"] += 1
                if event.severity in {"high", "critical"}:
                    buckets[label]["high_risk"] += 1
                if event.is_simulated:
                    buckets[label]["simulated"] += 1
    return list(buckets.values())


def _daily_activity(db: Session, org_id: int, days: int = 14) -> list[dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(Trip.start_time, Trip.distance_km, Trip.events_count)
        .filter(Trip.organisation_id == org_id, Trip.start_time >= since)
        .all()
    )
    buckets: dict[str, dict[str, Any]] = {}
    for i in range(days - 1, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).date()
        buckets[day.isoformat()] = {"date": day.strftime("%d %b"), "distance_km": 0.0, "trips": 0, "events": 0}
    for start_time, distance, events in rows:
        key = start_time.date().isoformat()
        if key in buckets:
            buckets[key]["distance_km"] += float(distance or 0)
            buckets[key]["trips"] += 1
            buckets[key]["events"] += int(events or 0)
    return list(buckets.values())


def dashboard_summary(db: Session, org_id: int, days: int = 30, user=None) -> dict[str, Any]:
    now = datetime.utcnow()
    since = now - timedelta(days=days)

    vehicles = db.query(Vehicle).filter(Vehicle.organisation_id == org_id, Vehicle.is_archived.is_(False)).all()
    drivers = db.query(Driver).filter(Driver.organisation_id == org_id).all()

    status_counts = {"active": 0, "inactive": 0, "under_maintenance": 0, "offline": 0}
    for vehicle in vehicles:
        status_counts[vehicle.status] = status_counts.get(vehicle.status, 0) + 1

    distance_total = float(
        db.query(func.coalesce(func.sum(Trip.distance_km), 0.0)).filter(Trip.organisation_id == org_id).scalar() or 0.0
    )
    distance_period = float(
        db.query(func.coalesce(func.sum(Trip.distance_km), 0.0))
        .filter(Trip.organisation_id == org_id, Trip.start_time >= since)
        .scalar()
        or 0.0
    )
    trips_period = int(
        db.query(func.count(Trip.id))
        .filter(Trip.organisation_id == org_id, Trip.start_time >= since)
        .scalar()
        or 0
    )

    event_rows = (
        db.query(DrivingEvent)
        .filter(DrivingEvent.organisation_id == org_id, DrivingEvent.occurred_at >= since)
        .all()
    )
    high_risk = sum(1 for e in event_rows if e.severity in {"high", "critical"})
    critical = sum(1 for e in event_rows if e.severity == "critical")
    simulated_events = sum(1 for e in event_rows if e.is_simulated)

    by_type: dict[str, int] = {}
    by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for event in event_rows:
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
        by_severity[event.severity] = by_severity.get(event.severity, 0) + 1

    latest_scores = (
        db.query(DriverScore)
        .filter(
            DriverScore.organisation_id == org_id,
            DriverScore.period == "weekly",
            DriverScore.period_start >= since - timedelta(days=7),
        )
        .order_by(DriverScore.period_start.desc())
        .all()
    )
    seen: set[int] = set()
    current_scores: list[DriverScore] = []
    for score in latest_scores:
        if score.driver_id in seen:
            continue
        seen.add(score.driver_id)
        current_scores.append(score)
    avg_score = round(sum(s.overall_score for s in current_scores) / len(current_scores), 1) if current_scores else 0.0
    avg_confidence = round(sum(s.confidence for s in current_scores) / len(current_scores), 2) if current_scores else 0.0

    open_maintenance = int(
        db.query(func.count(MaintenanceAlert.id))
        .filter(MaintenanceAlert.organisation_id == org_id, MaintenanceAlert.status == "open")
        .scalar()
        or 0
    )
    critical_maintenance = int(
        db.query(func.count(MaintenanceAlert.id))
        .filter(
            MaintenanceAlert.organisation_id == org_id,
            MaintenanceAlert.status == "open",
            MaintenanceAlert.severity == "high",
        )
        .scalar()
        or 0
    )

    incidents = (
        db.query(Incident)
        .filter(Incident.organisation_id == org_id, Incident.status != "false_alert")
        .order_by(Incident.occurred_at.desc())
        .all()
    )
    open_incidents = sum(1 for i in incidents if i.status in {"new", "under_investigation"})
    critical_incidents = sum(1 for i in incidents if i.severity == "critical" and i.status != "resolved")

    leaderboard = sorted(current_scores, key=lambda s: s.overall_score, reverse=True)[:5]
    leaderboard_rows = []
    driver_map = {d.id: d for d in drivers}
    for score in leaderboard:
        driver = driver_map.get(score.driver_id)
        leaderboard_rows.append(
            {
                "driver_id": score.driver_id,
                "driver_name": driver.full_name if driver else "Unknown",
                "score": score.overall_score,
                "events": score.events_count,
                "distance_km": score.distance_km,
                "avatar_color": driver.avatar_color if driver else "#0e7490",
            }
        )

    # Vehicle health: latest reading per vehicle.
    health_rows: dict[int, VehicleHealthReading] = {}
    for reading in (
        db.query(VehicleHealthReading)
        .filter(VehicleHealthReading.organisation_id == org_id)
        .order_by(VehicleHealthReading.recorded_at.desc())
        .all()
    ):
        if reading.vehicle_id not in health_rows:
            health_rows[reading.vehicle_id] = reading
    vehicle_health = []
    for vehicle in vehicles[:8]:
        reading = health_rows.get(vehicle.id)
        vehicle_health.append(
            {
                "vehicle_id": vehicle.id,
                "registration_number": vehicle.registration_number,
                "status": vehicle.status,
                "health_score": reading.health_score if reading else None,
                "fault_codes": reading.fault_codes if reading else [],
                "is_simulated": bool(reading.is_simulated) if reading else False,
                "mileage_km": vehicle.mileage_km,
            }
        )

    licences_expiring = sum(
        1
        for driver in drivers
        if driver.licence_expiry and (driver.licence_expiry - now.date()).days <= 30
    )

    recent_incidents = [
        {
            "id": i.id,
            "title": i.title,
            "severity": i.severity,
            "status": i.status,
            "occurred_at": i.occurred_at.isoformat(),
            "registration_number": i.vehicle.registration_number if i.vehicle else None,
            "driver_name": i.driver.full_name if i.driver else None,
        }
        for i in incidents[:5]
    ]

    from app.models import Notification

    notifications_query = db.query(Notification).filter(Notification.organisation_id == org_id)
    if user is not None:
        notifications_query = notifications_query.filter(Notification.user_id == user.id)
    recent_notifications = [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "priority": n.priority,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications_query.order_by(Notification.created_at.desc()).limit(6).all()
    ]

    distance_total = round(distance_total, 1)
    distance_period = round(distance_period, 1)

    return {
        "generated_at": now.isoformat() + "Z",
        "period_days": days,
        "kpis": {
            "total_vehicles": len(vehicles),
            "active_vehicles": status_counts["active"],
            "inactive_vehicles": status_counts["inactive"],
            "under_maintenance": status_counts["under_maintenance"],
            "offline_vehicles": status_counts["offline"],
            "total_drivers": len(drivers),
            "active_drivers": sum(1 for d in drivers if d.status == "active"),
            "total_distance_km": distance_total,
            "distance_period_km": distance_period,
            "trips_period": trips_period,
            "total_events": len(event_rows),
            "high_risk_events": high_risk,
            "critical_events": critical,
            "avg_driver_score": avg_score,
            "score_confidence": avg_confidence,
            "maintenance_alerts": open_maintenance,
            "critical_maintenance_alerts": critical_maintenance,
            "open_incidents": open_incidents,
            "critical_incidents": critical_incidents,
            "licences_expiring": licences_expiring,
            "simulated_share_pct": round(simulated_events / len(event_rows) * 100, 1) if event_rows else 0.0,
        },
        "trend": _weekly_trend(db, org_id, 8),
        "events_by_type": [{"type": k, "count": v} for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])],
        "events_by_severity": [{"severity": k, "count": v} for k, v in by_severity.items()],
        "vehicle_activity": _daily_activity(db, org_id, 14),
        "leaderboard": leaderboard_rows,
        "vehicle_health": vehicle_health,
        "recent_incidents": recent_incidents,
        "recent_notifications": recent_notifications,
        "disclaimer": (
            "Simulated telemetry is clearly labelled and does not represent real vehicles or drivers. "
            "Safety scores and risk levels support coaching; they do not predict accidents."
        ),
    }
