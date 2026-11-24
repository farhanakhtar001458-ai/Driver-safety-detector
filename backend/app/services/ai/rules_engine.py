"""Explainable driving-event detection and repeated-pattern analysis.

Everything in this module is transparent: thresholds are explicit, each event
records the measured value that triggered it, and no event is presented as a
confirmed violation. Camera-derived signals are labelled as low-confidence
observations and never treated as proven infractions.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import DrivingEvent, Driver, Organisation, Vehicle

# --------------------------------------------------------------------------
# Thresholds (configurable per organisation through settings_json)
# --------------------------------------------------------------------------
DEFAULT_THRESHOLDS: dict[str, float] = {
    "speeding_margin_kph": 5.0,
    "severe_speeding_margin_kph": 20.0,
    "harsh_braking_decel_mps2": 3.0,
    "severe_braking_decel_mps2": 4.5,
    "rapid_acceleration_mps2": 2.5,
    "severe_acceleration_mps2": 3.8,
    "aggressive_cornering_lateral_mps2": 3.0,
    "continuous_driving_hours": 4.5,
    "idle_minutes": 10.0,
}

SPEED_LIMITS_BY_TYPE: dict[str, float] = {
    "car": 70.0,
    "van": 60.0,
    "truck": 55.0,
    "bus": 55.0,
    "bike": 60.0,
    "electric": 70.0,
}

RECOMMENDED_ACTIONS: dict[str, str] = {
    "speeding": "Follow the posted speed limit and use cruise control where safe.",
    "harsh_braking": "Increase following distance and anticipate signals early.",
    "rapid_acceleration": "Accelerate smoothly; avoid full-throttle starts in traffic.",
    "aggressive_cornering": "Reduce speed before corners and avoid braking mid-turn.",
    "excessive_duration": "Take a break at least every 4.5 hours of continuous driving.",
    "seatbelt_violation": "Confirm the seatbelt is fastened before moving off.",
    "possible_distraction": "Review the flagged moment; keep devices stowed while driving.",
    "collision_suspected": "Verify driver safety first, then record the incident details.",
    "geofence_breach": "Check the route plan and confirm whether the deviation was authorised.",
    "route_deviation": "Confirm the route with the driver; record the reason for deviation.",
    "idle_excess": "Switch off the engine during long stationary periods.",
}

CATEGORY_FOR_EVENT: dict[str, str] = {
    "speeding": "speed",
    "harsh_braking": "braking",
    "rapid_acceleration": "acceleration",
    "aggressive_cornering": "cornering",
    "seatbelt_violation": "seatbelt",
    "possible_distraction": "distraction",
    "excessive_duration": "duration",
    "collision_suspected": "collision",
    "geofence_breach": "compliance",
    "route_deviation": "compliance",
    "idle_excess": "efficiency",
}


def get_thresholds(organisation: Organisation | None) -> dict[str, float]:
    """Organisation-level overrides live in ``settings_json['behaviour']``."""
    thresholds = dict(DEFAULT_THRESHOLDS)
    if organisation and organisation.settings_json:
        overrides = organisation.settings_json.get("behaviour", {})
        if isinstance(overrides, dict):
            for key, value in overrides.items():
                if key in thresholds and isinstance(value, (int, float)):
                    thresholds[key] = float(value)
    return thresholds


def speed_limit_for(vehicle: Vehicle | None, default: float = 60.0) -> float:
    if vehicle is None:
        return default
    return SPEED_LIMITS_BY_TYPE.get(vehicle.vehicle_type.lower(), default)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(a))


def _severity_for_speeding(margin: float, thresholds: dict[str, float]) -> str:
    if margin >= 30:
        return "critical"
    if margin >= thresholds["severe_speeding_margin_kph"]:
        return "high"
    if margin >= 10:
        return "medium"
    return "low"


def detect_events(
    prev: dict[str, Any],
    current: dict[str, Any],
    thresholds: dict[str, float],
    speed_limit_kph: float = 60.0,
    vehicle_type: str = "car",
) -> list[dict[str, Any]]:
    """Detect events between two telemetry samples.

    ``prev`` / ``current`` are dictionaries with latitude, longitude, speed_kph,
    heading, recorded_at (datetime) keys.
    """
    events: list[dict[str, Any]] = []
    dt = (current["recorded_at"] - prev["recorded_at"]).total_seconds()
    if dt <= 0 or dt > 300:  # ignore gaps / replayed data
        return events

    prev_speed = float(prev.get("speed_kph") or 0.0)
    cur_speed = float(current.get("speed_kph") or 0.0)
    limit = float(speed_limit_kph)

    # 1. Speeding -----------------------------------------------------------
    margin = cur_speed - limit
    if margin >= thresholds["speeding_margin_kph"]:
        events.append(
            {
                "event_type": "speeding",
                "severity": _severity_for_speeding(margin, thresholds),
                "speed_kph": cur_speed,
                "speed_limit_kph": limit,
                "sensor_data": {
                    "measured_speed_kph": round(cur_speed, 1),
                    "limit_kph": limit,
                    "excess_kph": round(margin, 1),
                    "sample_interval_s": round(dt, 1),
                },
                "recommended_action": RECOMMENDED_ACTIONS["speeding"],
                "measured_value": round(margin, 1),
            }
        )

    # 2. Harsh braking ------------------------------------------------------
    decel = (prev_speed - cur_speed) / 3.6 / dt  # m/s^2
    if decel >= thresholds["harsh_braking_decel_mps2"]:
        severity = (
            "critical" if decel >= 6.0 else "high" if decel >= thresholds["severe_braking_decel_mps2"] else "medium"
        )
        events.append(
            {
                "event_type": "harsh_braking",
                "severity": severity,
                "speed_kph": cur_speed,
                "speed_limit_kph": limit,
                "sensor_data": {
                    "deceleration_mps2": round(decel, 2),
                    "speed_before_kph": round(prev_speed, 1),
                    "speed_after_kph": round(cur_speed, 1),
                    "sample_interval_s": round(dt, 1),
                },
                "recommended_action": RECOMMENDED_ACTIONS["harsh_braking"],
                "measured_value": round(decel, 2),
            }
        )

    # 3. Rapid acceleration -------------------------------------------------
    accel = (cur_speed - prev_speed) / 3.6 / dt
    if accel >= thresholds["rapid_acceleration_mps2"]:
        severity = (
            "high" if accel >= 5.0 else "medium" if accel >= thresholds["severe_acceleration_mps2"] else "low"
        )
        events.append(
            {
                "event_type": "rapid_acceleration",
                "severity": severity,
                "speed_kph": cur_speed,
                "speed_limit_kph": limit,
                "sensor_data": {
                    "acceleration_mps2": round(accel, 2),
                    "speed_before_kph": round(prev_speed, 1),
                    "speed_after_kph": round(cur_speed, 1),
                    "sample_interval_s": round(dt, 1),
                },
                "recommended_action": RECOMMENDED_ACTIONS["rapid_acceleration"],
                "measured_value": round(accel, 2),
            }
        )

    # 4. Aggressive cornering (lateral acceleration from heading change) -----
    heading_delta = abs((float(current.get("heading", 0)) - float(prev.get("heading", 0)) + 540) % 360 - 180)
    if heading_delta > 8 and cur_speed > 25:
        lateral = (cur_speed / 3.6) * math.radians(heading_delta) / dt
        if lateral >= thresholds["aggressive_cornering_lateral_mps2"]:
            severity = (
                "critical" if lateral >= 6.0 else "high" if lateral >= 4.5 else "medium"
            )
            events.append(
                {
                    "event_type": "aggressive_cornering",
                    "severity": severity,
                    "speed_kph": cur_speed,
                    "speed_limit_kph": limit,
                    "sensor_data": {
                        "lateral_acceleration_mps2": round(lateral, 2),
                        "heading_change_deg": round(heading_delta, 1),
                        "speed_kph": round(cur_speed, 1),
                    },
                    "recommended_action": RECOMMENDED_ACTIONS["aggressive_cornering"],
                    "measured_value": round(lateral, 2),
                }
            )

    # 5. Excessive idling ---------------------------------------------------
    if cur_speed < 2 and prev_speed < 2 and dt >= 60:
        events.append(
            {
                "event_type": "idle_excess",
                "severity": "low",
                "speed_kph": cur_speed,
                "speed_limit_kph": limit,
                "sensor_data": {"stationary_seconds": round(dt, 0)},
                "recommended_action": RECOMMENDED_ACTIONS["idle_excess"],
            }
        )

    for event in events:
        event.update(
            {
                "latitude": current.get("latitude"),
                "longitude": current.get("longitude"),
                "occurred_at": current.get("recorded_at"),
                "source": current.get("source", "device"),
                "is_simulated": bool(current.get("is_simulated", False)),
            }
        )
    return events


def excessive_duration_event(started_at: datetime, ended_at: datetime) -> Optional[dict[str, Any]]:
    hours = (ended_at - started_at).total_seconds() / 3600
    if hours < DEFAULT_THRESHOLDS["continuous_driving_hours"]:
        return None
    severity = "critical" if hours >= 6 else "high"
    return {
        "event_type": "excessive_duration",
        "severity": severity,
        "sensor_data": {"continuous_driving_hours": round(hours, 2)},
        "recommended_action": RECOMMENDED_ACTIONS["excessive_duration"],
        "measured_value": round(hours, 2),
    }


# --------------------------------------------------------------------------
# Aggregation helpers
# --------------------------------------------------------------------------
SEVERITY_WEIGHTS = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def summarise(events: Iterable[DrivingEvent]) -> dict[str, Any]:
    event_list = list(events)
    by_type = Counter(e.event_type for e in event_list)
    by_severity = Counter(e.severity for e in event_list)
    weighted = sum(SEVERITY_WEIGHTS.get(e.severity, 1) for e in event_list)
    return {
        "total": len(event_list),
        "high_risk": sum(1 for e in event_list if e.severity in {"high", "critical"}),
        "critical": by_severity.get("critical", 0),
        "by_type": [{"event_type": k, "count": v} for k, v in by_type.most_common()],
        "by_severity": [{"severity": k, "count": by_severity.get(k, 0)} for k in ("low", "medium", "high", "critical")],
        "weighted_risk_points": weighted,
    }


def event_rate_per_100km(count: int, distance_km: float) -> float:
    if distance_km <= 0:
        return 0.0 if count == 0 else float(count) * 10
    return count / distance_km * 100.0


def analyse_patterns(db: Session, organisation_id: int, days: int = 30) -> list[dict[str, Any]]:
    """Detect repeated unsafe patterns.

    These are descriptive statistics over recorded events, not predictions.
    Each pattern includes the evidence used so a safety officer can verify it.
    """
    since = datetime.utcnow() - timedelta(days=days)
    events = (
        db.query(DrivingEvent)
        .filter(
            DrivingEvent.organisation_id == organisation_id,
            DrivingEvent.occurred_at >= since,
            DrivingEvent.driver_id.isnot(None),
        )
        .all()
    )
    patterns: list[dict[str, Any]] = []
    if not events:
        return patterns

    by_driver: dict[int, list[DrivingEvent]] = defaultdict(list)
    for event in events:
        by_driver[event.driver_id].append(event)  # type: ignore[index]

    drivers = {
        d.id: d
        for d in db.query(Driver).filter(Driver.organisation_id == organisation_id).all()
    }

    # --- Repeated speeding -------------------------------------------------
    repeat_speeders = []
    for driver_id, driver_events in by_driver.items():
        speeding = [e for e in driver_events if e.event_type == "speeding"]
        if len(speeding) >= 4:
            days_with = {e.occurred_at.date() for e in speeding}
            if len(days_with) >= 3:
                repeat_speeders.append(
                    {
                        "driver_id": driver_id,
                        "driver_name": drivers[driver_id].full_name if driver_id in drivers else f"Driver {driver_id}",
                        "events": len(speeding),
                        "days": len(days_with),
                        "max_excess_kph": max(
                            (e.sensor_data or {}).get("excess_kph", 0) for e in speeding
                        ),
                    }
                )
    if repeat_speeders:
        repeat_speeders.sort(key=lambda item: item["events"], reverse=True)
        patterns.append(
            {
                "key": "repeat_speeding",
                "title": "Repeated speeding on multiple days",
                "description": (
                    f"{len(repeat_speeders)} driver(s) recorded speeding on at least 3 separate days in the "
                    f"last {days} days, indicating a habitual pattern rather than an isolated event."
                ),
                "severity": "high",
                "affected_drivers": len(repeat_speeders),
                "evidence": {"drivers": repeat_speeders[:5], "threshold_events": 4, "threshold_days": 3},
                "recommended_action": "Assign targeted speed-management coaching and review route schedules for unrealistic delivery windows.",
                "confidence": 0.82,
            }
        )

    # --- Harsh braking clusters -------------------------------------------
    braking_drivers = []
    for driver_id, driver_events in by_driver.items():
        braking = [e for e in driver_events if e.event_type == "harsh_braking"]
        if len(braking) >= 3:
            braking_drivers.append(
                {
                    "driver_id": driver_id,
                    "driver_name": drivers[driver_id].full_name if driver_id in drivers else f"Driver {driver_id}",
                    "events": len(braking),
                    "avg_decel": round(
                        sum((e.sensor_data or {}).get("deceleration_mps2", 0) for e in braking) / len(braking), 2
                    ),
                }
            )
    if braking_drivers:
        braking_drivers.sort(key=lambda item: item["events"], reverse=True)
        patterns.append(
            {
                "key": "harsh_braking_cluster",
                "title": "Harsh braking concentrated in a few drivers",
                "description": (
                    f"{len(braking_drivers)} driver(s) account for repeated harsh-braking events. Clustering often "
                    "points to following-distance habits, traffic conditions or brake maintenance issues."
                ),
                "severity": "medium",
                "affected_drivers": len(braking_drivers),
                "evidence": {"drivers": braking_drivers[:5], "threshold_events": 3},
                "recommended_action": "Review following-distance coaching and inspect brake condition for the most affected vehicles.",
                "confidence": 0.78,
            }
        )

    # --- Night-time exposure ----------------------------------------------
    night = [e for e in events if e.occurred_at.hour >= 22 or e.occurred_at.hour < 5]
    if night and len(night) >= 5:
        night_share = len(night) / len(events) * 100
        patterns.append(
            {
                "key": "night_driving",
                "title": "Safety events during night hours",
                "description": (
                    f"{len(night)} of {len(events)} events ({night_share:.0f}%) occurred between 22:00 and 05:00, "
                    "when visibility and alertness are typically reduced."
                ),
                "severity": "medium",
                "affected_drivers": len({e.driver_id for e in night}),
                "evidence": {"events": len(night), "share_pct": round(night_share, 1), "window": "22:00-05:00"},
                "recommended_action": "Review night scheduling, rest breaks and headlight/visibility checks.",
                "confidence": 0.74,
            }
        )

    # --- Vehicle concentration --------------------------------------------
    by_vehicle: dict[int, list[DrivingEvent]] = defaultdict(list)
    for event in events:
        by_vehicle[event.vehicle_id].append(event)
    hot_vehicles = sorted(by_vehicle.items(), key=lambda kv: len(kv[1]), reverse=True)
    if hot_vehicles and len(hot_vehicles[0][1]) >= 6:
        vehicle = db.query(Vehicle).filter(Vehicle.id == hot_vehicles[0][0]).first()
        if vehicle:
            patterns.append(
                {
                    "key": "vehicle_concentration",
                    "title": f"Elevated event concentration on {vehicle.registration_number}",
                    "description": (
                        f"{len(hot_vehicles[0][1])} events were recorded on this vehicle in the period. "
                        "Concentration can reflect driver behaviour, route difficulty or a vehicle fault."
                    ),
                    "severity": "medium",
                    "affected_drivers": len({e.driver_id for e in hot_vehicles[0][1]}),
                    "evidence": {
                        "vehicle_id": vehicle.id,
                        "registration": vehicle.registration_number,
                        "events": len(hot_vehicles[0][1]),
                    },
                    "recommended_action": "Compare this vehicle's events with its assigned drivers and check for brake or tyre issues.",
                    "confidence": 0.7,
                }
            )

    # --- Data coverage note ------------------------------------------------
    simulated_share = sum(1 for e in events if e.is_simulated) / len(events) * 100
    if simulated_share > 50:
        patterns.append(
            {
                "key": "simulated_data",
                "title": "Most events come from simulated telemetry",
                "description": (
                    f"{simulated_share:.0f}% of events in this period are simulated demonstration data. "
                    "Patterns are illustrative and must not be used for employment decisions."
                ),
                "severity": "low",
                "affected_drivers": len(by_driver),
                "evidence": {"simulated_share_pct": round(simulated_share, 1)},
                "recommended_action": "Connect physical GPS devices before using these insights operationally.",
                "confidence": 0.99,
            }
        )

    patterns.sort(key=lambda p: {"critical": 0, "high": 1, "medium": 2, "low": 3}[p["severity"]])
    return patterns


def score_trend(db: Session, organisation_id: int, days: int = 8) -> list[dict[str, Any]]:
    """Weekly event trend used across dashboard and reports."""
    rows = (
        db.query(DrivingEvent.occurred_at, DrivingEvent.severity)
        .filter(
            DrivingEvent.organisation_id == organisation_id,
            DrivingEvent.occurred_at >= datetime.utcnow() - timedelta(days=days * 7),
        )
        .all()
    )
    buckets: dict[str, dict[str, Any]] = {}
    for i in range(days, 0, -1):
        start = (datetime.utcnow() - timedelta(days=7 * i)).date()
        label = start.strftime("%d %b")
        buckets[label] = {"period": label, "events": 0, "high_risk": 0}
    for occurred_at, severity in rows:
        label = (occurred_at - timedelta(days=0)).strftime("%d %b")
        # map to nearest week bucket
        week_start = (datetime.utcnow() - timedelta(days=7 * ((datetime.utcnow() - occurred_at).days // 7) + (datetime.utcnow() - occurred_at).days % 7)).strftime("%d %b")
        if week_start in buckets:
            buckets[week_start]["events"] += 1
            if severity in {"high", "critical"}:
                buckets[week_start]["high_risk"] += 1
    return list(buckets.values())
