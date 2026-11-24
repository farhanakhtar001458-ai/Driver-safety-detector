"""Transparent, configurable driver safety scoring (0-100).

Design principles
-----------------
* Every subscore is derived from a measurable event rate per 100 km.
* Categories with no data are excluded and their weight is renormalised, so
  missing sensors never silently punish a driver.
* Confidence is reported alongside the score and reduced when data is sparse.
* Scores describe observed behaviour; they are not a probability of crashing.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import DrivingEvent, Driver, DriverScore

DEFAULT_WEIGHTS: dict[str, float] = {
    "speed": 0.22,
    "braking": 0.18,
    "acceleration": 0.15,
    "cornering": 0.15,
    "seatbelt": 0.12,
    "consistency": 0.18,
}

# Penalty applied per event per 100 km. Higher = stricter.
CATEGORY_PENALTIES: dict[str, float] = {
    "speed": 2.2,
    "braking": 1.9,
    "acceleration": 1.6,
    "cornering": 1.7,
    "seatbelt": 5.0,
    "duration": 2.5,
}

CATEGORY_LABELS = {
    "speed": "Speed management",
    "braking": "Braking behaviour",
    "acceleration": "Acceleration behaviour",
    "cornering": "Cornering behaviour",
    "seatbelt": "Seatbelt compliance",
    "consistency": "Driving consistency",
}

DISCLAIMER = (
    "Safety scores summarise recorded driving behaviour and are intended for coaching. "
    "They do not measure crash probability and should not be used as the sole basis for "
    "disciplinary action."
)


def get_weights(organisation) -> dict[str, float]:
    weights = dict(DEFAULT_WEIGHTS)
    if organisation and organisation.settings_json:
        overrides = organisation.settings_json.get("score_weights")
        if isinstance(overrides, dict):
            cleaned = {}
            for key, value in overrides.items():
                if key in weights and isinstance(value, (int, float)) and value >= 0:
                    cleaned[key] = float(value)
            if cleaned and sum(cleaned.values()) > 0:
                weights.update(cleaned)
    total = sum(weights.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {key: value / total for key, value in weights.items()}


def _category_score(event_count: int, distance_km: float, penalty: float) -> float:
    if event_count == 0:
        return 100.0
    effective_distance = max(distance_km, 10.0)
    rate = event_count / effective_distance * 100.0
    return max(0.0, 100.0 * (2.718281828 ** (-rate * penalty * 0.28)))


def _consistency_score(events: list[DrivingEvent]) -> float:
    """Consistency rewards steady speeds; measured from speeding event spread."""
    speeding = [e for e in events if e.event_type == "speeding"]
    if not speeding:
        return 100.0
    excesses = [(e.sensor_data or {}).get("excess_kph", 0) for e in speeding]
    if not excesses:
        return 90.0
    mean = sum(excesses) / len(excesses)
    variance = sum((value - mean) ** 2 for value in excesses) / len(excesses)
    # Higher variance and higher mean both reduce consistency.
    return max(0.0, min(100.0, 100.0 - (mean * 1.8) - (variance ** 0.5) * 1.2))


def compute_score(
    events: list[DrivingEvent],
    distance_km: float,
    weights: Optional[dict[str, float]] = None,
    *,
    seatbelt_data_available: Optional[bool] = None,
    is_simulated: bool = False,
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
) -> dict[str, Any]:
    weights = weights or dict(DEFAULT_WEIGHTS)
    counts = {
        "speed": sum(1 for e in events if e.event_type == "speeding"),
        "braking": sum(1 for e in events if e.event_type == "harsh_braking"),
        "acceleration": sum(1 for e in events if e.event_type == "rapid_acceleration"),
        "cornering": sum(1 for e in events if e.event_type == "aggressive_cornering"),
        "seatbelt": sum(1 for e in events if e.event_type == "seatbelt_violation"),
        "duration": sum(1 for e in events if e.event_type == "excessive_duration"),
    }

    subscores = {
        "speed": _category_score(counts["speed"], distance_km, CATEGORY_PENALTIES["speed"]),
        "braking": _category_score(counts["braking"], distance_km, CATEGORY_PENALTIES["braking"]),
        "acceleration": _category_score(counts["acceleration"], distance_km, CATEGORY_PENALTIES["acceleration"]),
        "cornering": _category_score(counts["cornering"], distance_km, CATEGORY_PENALTIES["cornering"]),
        "consistency": _consistency_score(events),
    }

    seatbelt_available = (
        seatbelt_data_available
        if seatbelt_data_available is not None
        else (counts["seatbelt"] > 0)
    )
    if seatbelt_available:
        subscores["seatbelt"] = _category_score(counts["seatbelt"], distance_km, CATEGORY_PENALTIES["seatbelt"])
    else:
        subscores["seatbelt"] = None

    active_weights = {key: value for key, value in weights.items() if subscores.get(key) is not None}
    total_weight = sum(active_weights.values()) or 1.0
    overall = sum(subscores[key] * weight for key, weight in active_weights.items()) / total_weight

    confidence = 0.9
    if distance_km < 20:
        confidence -= 0.2
    if not seatbelt_available:
        confidence -= 0.12
    if is_simulated:
        confidence -= 0.08
    if len(events) == 0 and distance_km < 10:
        confidence -= 0.2
    confidence = round(max(0.2, min(0.95, confidence)), 2)

    breakdown = {
        "counts": counts,
        "subscores": {key: round(value, 1) if value is not None else None for key, value in subscores.items()},
        "weights_used": {key: round(value / total_weight, 4) for key, value in active_weights.items()},
        "excluded_categories": [key for key, value in subscores.items() if value is None],
        "events_per_100km": round(len(events) / max(distance_km, 10) * 100, 2),
        "method": "weighted_exponential_decay_v1",
    }

    return {
        "overall": round(overall, 1),
        "speed": round(subscores["speed"], 1),
        "braking": round(subscores["braking"], 1),
        "acceleration": round(subscores["acceleration"], 1),
        "cornering": round(subscores["cornering"], 1),
        "seatbelt": round(subscores["seatbelt"], 1) if subscores["seatbelt"] is not None else None,
        "consistency": round(subscores["consistency"], 1),
        "events_count": len(events),
        "distance_km": round(distance_km, 1),
        "confidence": confidence,
        "breakdown": breakdown,
    }


def _period_distance(db: Session, driver_id: int, start: datetime, end: datetime) -> float:
    from sqlalchemy import func

    from app.models import Trip

    total = (
        db.query(func.coalesce(func.sum(Trip.distance_km), 0.0))
        .filter(
            Trip.driver_id == driver_id,
            Trip.start_time >= start,
            Trip.start_time <= end,
        )
        .scalar()
    )
    return float(total or 0.0)


def compute_driver_period_score(
    db: Session,
    driver: Driver,
    period: str,
    period_start: datetime,
    period_end: datetime,
    organisation=None,
) -> DriverScore:
    events = (
        db.query(DrivingEvent)
        .filter(
            DrivingEvent.driver_id == driver.id,
            DrivingEvent.occurred_at >= period_start,
            DrivingEvent.occurred_at <= period_end,
        )
        .all()
    )
    distance_km = _period_distance(db, driver.id, period_start, period_end)
    weights = get_weights(organisation)
    simulated_share = sum(1 for e in events if e.is_simulated)
    result = compute_score(
        events,
        distance_km,
        weights,
        is_simulated=bool(events) and simulated_share / len(events) > 0.5,
    )

    score = (
        db.query(DriverScore)
        .filter(
            DriverScore.driver_id == driver.id,
            DriverScore.period == period,
            DriverScore.period_start == period_start,
        )
        .first()
    )
    if not score:
        score = DriverScore(
            driver_id=driver.id,
            organisation_id=driver.organisation_id,
            period=period,
            period_start=period_start,
            period_end=period_end,
        )
        db.add(score)

    score.overall_score = result["overall"]
    score.speed_score = result["speed"]
    score.braking_score = result["braking"]
    score.acceleration_score = result["acceleration"]
    score.cornering_score = result["cornering"]
    score.seatbelt_score = result["seatbelt"]
    score.consistency_score = result["consistency"]
    score.events_count = result["events_count"]
    score.distance_km = result["distance_km"]
    score.confidence = result["confidence"]
    score.breakdown = result["breakdown"]
    score.model_version = settings.SCORING_MODEL_VERSION
    db.flush()
    return score


def compute_driver_scores(db: Session, driver: Driver, organisation=None) -> dict[str, DriverScore]:
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    scores = {
        "daily": compute_driver_period_score(db, driver, "daily", today, now, organisation),
        "weekly": compute_driver_period_score(db, driver, "weekly", week_start, now, organisation),
        "monthly": compute_driver_period_score(db, driver, "monthly", month_start, now, organisation),
        "overall": compute_driver_period_score(
            db, driver, "overall", now - timedelta(days=365), now, organisation
        ),
    }
    return scores


def score_history(db: Session, driver_id: int, periods: int = 8) -> list[DriverScore]:
    return (
        db.query(DriverScore)
        .filter(DriverScore.driver_id == driver_id, DriverScore.period == "weekly")
        .order_by(DriverScore.period_start.desc())
        .limit(periods)
        .all()
    )


def recommendations_for(score: DriverScore) -> list[str]:
    recommendations: list[str] = []
    if score.speed_score < 80:
        recommendations.append("Focus on speed management: keep a steady pace and observe posted limits.")
    if score.braking_score < 80:
        recommendations.append("Practise earlier braking and maintain a safe following distance.")
    if score.acceleration_score < 80:
        recommendations.append("Smooth out acceleration, especially when loaded or carrying passengers.")
    if score.cornering_score < 80:
        recommendations.append("Slow down before corners and avoid sharp steering inputs.")
    if score.seatbelt_score is not None and score.seatbelt_score < 95:
        recommendations.append("Make seatbelt checks part of the pre-trip routine.")
    if score.consistency_score < 75:
        recommendations.append("Aim for consistent speeds; variability often signals late reactions.")
    if not recommendations:
        recommendations.append("Maintain current driving standards and complete refresher training periodically.")
    return recommendations
