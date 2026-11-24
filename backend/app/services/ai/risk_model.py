"""Fleet risk assessment: gradient boosting + transparent safety rules.

The classifier is trained on a **synthetic** historical dataset generated with a
fixed random seed. That dataset is documented and labelled; it is not real crash
data. The model output is a triage priority score, not an accident prediction.

Model transparency
------------------
* Feature list is explicit and versioned.
* Global permutation importances are reported.
* Every assessment stores the exact input feature values.
* Rule-based indicators accompany the probability so a reviewer can see *why*
  a driver was flagged, and can disagree with the model.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.inspection import permutation_importance

from app.core.config import settings
from app.models import (
    DrivingEvent,
    Driver,
    DriverScore,
    Incident,
    MaintenanceAlert,
    RiskAssessment,
    Trip,
    Vehicle,
    VehicleHealthReading,
)

FEATURE_NAMES = [
    "events_per_100km",
    "speeding_rate",
    "harsh_braking_rate",
    "rapid_acceleration_rate",
    "cornering_rate",
    "night_event_share",
    "avg_speed_kph",
    "max_speed_kph",
    "continuous_driving_hours",
    "distance_km",
    "vehicle_age_years",
    "vehicle_health_score",
    "open_maintenance_alerts",
    "licence_days_to_expiry",
    "incidents_12m",
    "safety_score_30d",
]

MODEL_VERSION = settings.RISK_MODEL_VERSION
SYNTHETIC_TRAINING_ROWS = 6000

_MODEL: Optional[HistGradientBoostingClassifier] = None
_METRICS: dict[str, Any] = {}
_IMPORTANCE: dict[str, float] = {}
_TRAINING_SUMMARY: dict[str, Any] = {}

DISCLAIMER = (
    "Risk assessments prioritise safety review. They do not predict when or whether "
    "an accident will happen, and must not be used as the sole basis for disciplinary "
    "or employment decisions."
)


# --------------------------------------------------------------------------
# Synthetic training data
# --------------------------------------------------------------------------
@dataclass
class SyntheticRow:
    events_per_100km: float
    speeding_rate: float
    harsh_braking_rate: float
    rapid_acceleration_rate: float
    cornering_rate: float
    night_event_share: float
    avg_speed_kph: float
    max_speed_kph: float
    continuous_driving_hours: float
    distance_km: float
    vehicle_age_years: float
    vehicle_health_score: float
    open_maintenance_alerts: float
    licence_days_to_expiry: float
    incidents_12m: float
    safety_score_30d: float
    label: int


def _generate_training_data(rows: int = SYNTHETIC_TRAINING_ROWS, seed: int = 42) -> list[SyntheticRow]:
    """Generate a reproducible synthetic historical dataset.

    The data-generating process mimics realistic correlations: high event rates,
    night exposure, poor vehicle health and high mileage all increase the latent
    risk, while high safety scores reduce it. Labels are noisy by design so the
    model learns a ranking rather than a deterministic mapping.
    """
    rng = np.random.default_rng(seed)
    data: list[SyntheticRow] = []
    for _ in range(rows):
        exposure = float(np.clip(rng.gamma(2.0, 900.0), 50, 15000))
        style = float(np.clip(rng.beta(2.0, 5.0), 0, 1))  # latent unsafe driving style
        events_per_100km = float(np.clip(rng.gamma(1.8, 1.1) + style * 6.0, 0, 25))
        speeding_rate = float(np.clip(events_per_100km * rng.uniform(0.25, 0.55), 0, 18))
        harsh_braking_rate = float(np.clip(events_per_100km * rng.uniform(0.1, 0.3), 0, 10))
        rapid_acceleration_rate = float(np.clip(events_per_100km * rng.uniform(0.08, 0.25), 0, 8))
        cornering_rate = float(np.clip(events_per_100km * rng.uniform(0.05, 0.2), 0, 6))
        night_share = float(np.clip(rng.beta(1.5, 6.0) + style * 0.15, 0, 1))
        avg_speed = float(np.clip(rng.normal(48, 12) + style * 6, 15, 110))
        max_speed = float(np.clip(avg_speed + rng.uniform(15, 55) + style * 15, 20, 160))
        continuous = float(np.clip(rng.gamma(1.6, 1.1), 0.2, 11))
        vehicle_age = float(np.clip(rng.uniform(0, 14) + style * 1.5, 0, 22))
        health = float(np.clip(100 - vehicle_age * 3.2 - style * 12 + rng.normal(0, 7), 20, 100))
        open_maintenance_alerts = 1.0 if (rng.random() < (0.1 + style * 0.25 + vehicle_age / 80)) else 0.0
        licence_days = float(np.clip(rng.normal(260, 200), -60, 730))
        incidents = float(np.clip(rng.poisson(0.35 + style * 2.5 + open_maintenance_alerts * 0.6), 0, 12))
        score = float(np.clip(96 - style * 34 + rng.normal(0, 6), 20, 100))

        # Latent risk: transparent additive combination. The label is derived from
        # this score with a small amount of noise, which keeps the learning task
        # realistic (imperfect labels) while preserving a learnable signal.
        latent = (
            0.10 * speeding_rate
            + 0.075 * harsh_braking_rate
            + 0.05 * rapid_acceleration_rate
            + 0.04 * cornering_rate
            + 0.11 * night_share
            + 0.006 * max(0, max_speed - 90)
            + 0.14 * max(0, continuous - 4.5)
            + 0.02 * vehicle_age
            + 0.014 * (100 - health)
            + 0.6 * open_maintenance_alerts
            + 0.22 * incidents
            - 0.022 * (score - 70)
            + 0.00004 * exposure
            - 1.1
        )
        probability = 1 / (1 + math.exp(-latent * 2.4))
        label = int(probability > 0.5)
        if rng.random() < 0.08:  # 8% label noise
            label = 1 - label
        data.append(
            SyntheticRow(
                events_per_100km=round(events_per_100km, 2),
                speeding_rate=round(speeding_rate, 2),
                harsh_braking_rate=round(harsh_braking_rate, 2),
                rapid_acceleration_rate=round(rapid_acceleration_rate, 2),
                cornering_rate=round(cornering_rate, 2),
                night_event_share=round(night_share, 3),
                avg_speed_kph=round(avg_speed, 1),
                max_speed_kph=round(max_speed, 1),
                continuous_driving_hours=round(continuous, 2),
                distance_km=round(exposure, 1),
                vehicle_age_years=round(vehicle_age, 1),
                vehicle_health_score=round(health, 1),
                open_maintenance_alerts=open_maintenance_alerts,
                licence_days_to_expiry=round(licence_days, 1),
                incidents_12m=float(incidents),
                safety_score_30d=round(score, 1),
                label=label,
            )
        )
    return data


def _matrix(rows: list[SyntheticRow]) -> tuple[np.ndarray, np.ndarray]:
    X = np.array([[getattr(row, name) for name in FEATURE_NAMES] for row in rows], dtype=float)
    y = np.array([row.label for row in rows], dtype=int)
    return X, y


def _train() -> None:
    global _MODEL, _METRICS, _IMPORTANCE, _TRAINING_SUMMARY
    rows = _generate_training_data()
    X, y = _matrix(rows)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    model = HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.06,
        max_depth=4,
        l2_regularization=1.0,
        min_samples_leaf=40,
        random_state=42,
    )
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)
    tn = int(((preds == 0) & (y_test == 0)).sum())
    fp = int(((preds == 1) & (y_test == 0)).sum())
    fn = int(((preds == 0) & (y_test == 1)).sum())
    tp = int(((preds == 1) & (y_test == 1)).sum())
    _METRICS = {
        "auc_roc": round(float(roc_auc_score(y_test, proba)), 3),
        "brier_score": round(float(brier_score_loss(y_test, proba)), 3),
        "accuracy": round(float((preds == y_test).mean()), 3),
        "false_positive_rate": round(fp / max(1, fp + tn), 3),
        "false_negative_rate": round(fn / max(1, fn + tp), 3),
        "precision": round(tp / max(1, tp + fp), 3),
        "recall": round(tp / max(1, tp + fn), 3),
        "holdout_rows": int(len(y_test)),
        "positive_rate": round(float(y_test.mean()), 3),
    }
    result = permutation_importance(model, X_test, y_test, n_repeats=6, random_state=42, scoring="roc_auc")
    _IMPORTANCE = {
        name: round(float(value), 4)
        for name, value in sorted(zip(FEATURE_NAMES, result.importances_mean), key=lambda kv: -abs(kv[1]))
    }
    _TRAINING_SUMMARY = {
        "dataset": "synthetic (seeded)",
        "rows": len(rows),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "features": FEATURE_NAMES,
    }
    _MODEL = model


def get_model() -> HistGradientBoostingClassifier:
    global _MODEL
    if _MODEL is None:
        _train()
    return _MODEL  # type: ignore[return-value]


def model_info() -> dict[str, Any]:
    get_model()
    return {
        "name": "Fleet Risk Classifier",
        "version": MODEL_VERSION,
        "type": "gradient_boosted_trees_plus_rules",
        "metrics": _METRICS,
        "feature_importance": _IMPORTANCE,
        "features": FEATURE_NAMES,
        "training": _TRAINING_SUMMARY,
        "limitations": [
            "Trained on synthetic historical data for demonstration, not on real crash records.",
            "Outputs are triage priorities, not accident predictions.",
            "Calibration is only reliable when most input features are available.",
            "Behavioural events depend on sensor quality and threshold configuration.",
        ],
        "disclaimer": DISCLAIMER,
    }


def predict(features: dict[str, float]) -> tuple[float, str]:
    model = get_model()
    vector = np.array([[float(features.get(name, 0.0)) for name in FEATURE_NAMES]])
    probability = float(model.predict_proba(vector)[0, 1])
    level = risk_level_from_score(probability)
    return probability, level


def risk_level_from_score(probability: float) -> str:
    if probability >= 0.75:
        return "critical"
    if probability >= 0.5:
        return "high"
    if probability >= 0.25:
        return "moderate"
    return "low"


def _latest_health(db: Session, vehicle_id: Optional[int]) -> Optional[VehicleHealthReading]:
    if not vehicle_id:
        return None
    return (
        db.query(VehicleHealthReading)
        .filter(VehicleHealthReading.vehicle_id == vehicle_id)
        .order_by(VehicleHealthReading.recorded_at.desc())
        .first()
    )


def build_driver_features(
    db: Session, driver: Driver, vehicle: Optional[Vehicle] = None, days: int = 90
) -> tuple[dict[str, float], dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=days)
    events = (
        db.query(DrivingEvent)
        .filter(DrivingEvent.driver_id == driver.id, DrivingEvent.occurred_at >= since)
        .all()
    )
    distance = float(
        db.query(func.coalesce(func.sum(Trip.distance_km), 0.0))
        .filter(Trip.driver_id == driver.id, Trip.start_time >= since)
        .scalar()
        or 0.0
    )
    effective_distance = max(distance, 10.0)

    def rate(event_type: str) -> float:
        return round(sum(1 for e in events if e.event_type == event_type) / effective_distance * 100, 2)

    speeds = [e.speed_kph for e in events if e.speed_kph is not None]
    night = [e for e in events if e.occurred_at.hour >= 22 or e.occurred_at.hour < 5]
    continuous = max(
        [(e.sensor_data or {}).get("continuous_driving_hours", 0) for e in events] or [0]
    )
    vehicle = vehicle or (
        db.query(Vehicle)
        .filter(Vehicle.assigned_driver_id == driver.id, Vehicle.is_archived.is_(False))
        .first()
    )
    health = _latest_health(db, vehicle.id if vehicle else None)
    now = datetime.utcnow()
    licence_days = (
        (driver.licence_expiry - now.date()).days if driver.licence_expiry else 365.0
    )
    incidents = (
        db.query(func.count(Incident.id))
        .filter(
            Incident.driver_id == driver.id,
            Incident.occurred_at >= now - timedelta(days=365),
            Incident.status != "false_alert",
        )
        .scalar()
        or 0
    )
    latest_score = (
        db.query(DriverScore)
        .filter(DriverScore.driver_id == driver.id)
        .order_by(DriverScore.period_end.desc())
        .first()
    )
    overdue_alerts = (
        db.query(func.count(MaintenanceAlert.id))
        .filter(
            MaintenanceAlert.vehicle_id == (vehicle.id if vehicle else -1),
            MaintenanceAlert.status == "open",
        )
        .scalar()
        or 0
    )
    vehicle_age = max(0, now.year - vehicle.manufacturing_year) if vehicle else 5.0
    features = {
        "events_per_100km": round(len(events) / effective_distance * 100, 2),
        "speeding_rate": rate("speeding"),
        "harsh_braking_rate": rate("harsh_braking"),
        "rapid_acceleration_rate": rate("rapid_acceleration"),
        "cornering_rate": rate("aggressive_cornering"),
        "night_event_share": round(len(night) / len(events), 3) if events else 0.0,
        "avg_speed_kph": round(sum(speeds) / len(speeds), 1) if speeds else 45.0,
        "max_speed_kph": round(max(speeds), 1) if speeds else 60.0,
        "continuous_driving_hours": round(float(continuous or 0), 2),
        "distance_km": round(distance, 1),
        "vehicle_age_years": round(float(vehicle_age), 1),
        "vehicle_health_score": round(health.health_score, 1) if health else 85.0,
        "open_maintenance_alerts": 1.0 if overdue_alerts > 0 else 0.0,
        "licence_days_to_expiry": round(float(licence_days), 1),
        "incidents_12m": float(incidents),
        "safety_score_30d": round(latest_score.overall_score, 1) if latest_score else 80.0,
    }
    context = {
        "events": len(events),
        "distance_km": round(distance, 1),
        "vehicle": vehicle,
        "health": health,
        "score": latest_score,
        "overdue_alerts": overdue_alerts,
        "incidents_12m": incidents,
        "licence_days": licence_days,
    }
    return features, context


def _rule_indicators(features: dict[str, float], context: dict[str, Any]) -> list[dict[str, Any]]:
    indicators: list[dict[str, Any]] = []

    def add(key: str, label: str, value: Any, detail: str, weight: float, direction: str = "risk") -> None:
        indicators.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "detail": detail,
                "weight": weight,
                "direction": direction,
            }
        )

    if features["speeding_rate"] >= 2.0:
        add(
            "speeding_rate",
            "Speeding rate above guideline",
            features["speeding_rate"],
            f"{features['speeding_rate']:.1f} speeding events per 100 km in the last 90 days.",
            3 if features["speeding_rate"] >= 5 else 2,
        )
    if features["harsh_braking_rate"] >= 1.2:
        add(
            "harsh_braking_rate",
            "Frequent harsh braking",
            features["harsh_braking_rate"],
            f"{features['harsh_braking_rate']:.1f} harsh-braking events per 100 km.",
            2,
        )
    if features["rapid_acceleration_rate"] >= 1.0:
        add(
            "rapid_acceleration_rate",
            "Rapid acceleration pattern",
            features["rapid_acceleration_rate"],
            f"{features['rapid_acceleration_rate']:.1f} rapid-acceleration events per 100 km.",
            1,
        )
    if features["night_event_share"] >= 0.3:
        add(
            "night_event_share",
            "High night-time event share",
            round(features["night_event_share"] * 100, 1),
            f"{features['night_event_share'] * 100:.0f}% of events occurred between 22:00 and 05:00.",
            2,
        )
    if features["continuous_driving_hours"] >= 4.5:
        add(
            "continuous_driving_hours",
            "Extended continuous driving",
            features["continuous_driving_hours"],
            f"Longest continuous driving period recorded: {features['continuous_driving_hours']:.1f} h.",
            2,
        )
    if features["vehicle_health_score"] < 70:
        add(
            "vehicle_health_score",
            "Vehicle health below threshold",
            features["vehicle_health_score"],
            "Latest diagnostic health score is below 70; maintenance review recommended.",
            2,
        )
    if features["open_maintenance_alerts"] >= 1:
        add(
            "open_maintenance_alerts",
            "Open maintenance alerts",
            int(context.get("overdue_alerts", 0)),
            "One or more maintenance alerts are still open for the assigned vehicle.",
            2,
        )
    if features["licence_days_to_expiry"] <= 30:
        add(
            "licence_days_to_expiry",
            "Driving licence expiring soon",
            int(features["licence_days_to_expiry"]),
            "Licence expires within 30 days; renewal should be completed before expiry.",
            2,
        )
    if features["incidents_12m"] >= 1:
        add(
            "incidents_12m",
            "Incident history in the last 12 months",
            int(features["incidents_12m"]),
            f"{int(features['incidents_12m'])} incident(s) recorded in the last 12 months.",
            3 if features["incidents_12m"] >= 2 else 2,
        )
    if features["safety_score_30d"] < 70:
        add(
            "safety_score_30d",
            "Safety score below 70",
            features["safety_score_30d"],
            "Recent behaviour score is below the 70-point coaching threshold.",
            2,
        )
    if features["distance_km"] >= 5000:
        add(
            "distance_km",
            "High mileage exposure",
            features["distance_km"],
            f"{features['distance_km']:.0f} km driven in 90 days increases exposure.",
            1,
        )
    if not indicators:
        add(
            "no_indicators",
            "No behavioural indicators triggered",
            "clear",
            "No configured safety rule flagged this driver in the review window.",
            0,
            "positive",
        )
    return indicators


def _explanation(level: str, probability: float, indicators: list[dict[str, Any]], coverage: dict[str, Any]) -> str:
    if level == "low":
        base = "This driver shows a low concentration of risk indicators in the review window. "
    else:
        base = f"This driver is classified as {level} risk based on {len([i for i in indicators if i['weight'] > 0])} indicator(s). "
    top = [i for i in indicators if i["weight"] > 0][:3]
    if top:
        base += "The main contributors are: " + "; ".join(i["detail"] for i in top)
    else:
        base += "No rule-based indicator was triggered; the score is driven by the behavioural model."
    if coverage.get("missing", 0) > 0:
        base += f" Note: {coverage['missing']} input feature(s) were unavailable and imputed with fleet defaults, which lowers confidence."
    base += " This is a review priority, not a prediction of an accident."
    return base


def _recommendations(indicators: list[dict[str, Any]], level: str) -> list[str]:
    recs: list[str] = []
    keys = {i["key"] for i in indicators}
    if "speeding_rate" in keys:
        recs.append("Complete a speed-management briefing and review route timing with the driver.")
    if "harsh_braking_rate" in keys:
        recs.append("Coach following distance and smooth braking; inspect brake wear on the assigned vehicle.")
    if "rapid_acceleration_rate" in keys:
        recs.append("Review smooth-acceleration technique, particularly when loaded.")
    if "night_event_share" in keys:
        recs.append("Review night-duty rosters and fatigue-management controls.")
    if "continuous_driving_hours" in keys:
        recs.append("Enforce rest breaks for journeys longer than 4.5 hours.")
    if "vehicle_health_score" in keys or "open_maintenance_alerts" in keys:
        recs.append("Schedule a vehicle inspection and clear open maintenance alerts.")
    if "licence_days_to_expiry" in keys:
        recs.append("Confirm licence renewal before the expiry date and record the new document.")
    if "incidents_12m" in keys:
        recs.append("Complete an incident review with the safety officer and document corrective actions.")
    if "safety_score_30d" in keys:
        recs.append("Assign a focused coaching plan and review progress in two weeks.")
    if not recs:
        recs.append("Continue routine monitoring and recognise the driver's safe behaviour.")
    if level in {"high", "critical"}:
        recs.append("Escalate to the safety officer for a documented review within 7 days.")
    return recs


def assess_driver(
    db: Session,
    driver: Driver,
    vehicle: Optional[Vehicle] = None,
    *,
    persist: bool = True,
) -> RiskAssessment:
    features, context = build_driver_features(db, driver, vehicle)
    probability, level = predict(features)
    indicators = _rule_indicators(features, context)

    # Rule overlay: documented, auditable adjustments to the model probability.
    rule_score = sum(i["weight"] for i in indicators) * 0.06
    combined = min(0.99, probability * 0.72 + rule_score * 0.6)
    level = risk_level_from_score(combined)

    missing = sum(
        1
        for key in ("vehicle_health_score", "safety_score_30d", "distance_km")
        if key == "vehicle_health_score" and not context.get("health")
    )
    missing += 0 if context.get("score") else 1
    confidence = round(max(0.3, min(0.92, 0.88 - missing * 0.15)), 2)
    explanation = _explanation(level, combined, indicators, {"missing": missing})
    recs = _recommendations(indicators, level)
    limitations = [
        "Model trained on synthetic historical data; validate against your own incident records before operational use.",
        "Camera-derived events are low-confidence observations and are not treated as confirmed violations.",
        "Risk level is a triage priority, not an accident prediction.",
    ]
    if context.get("score") is None:
        limitations.append("No recent safety score was available; a neutral default was used.")

    assessment = RiskAssessment(
        organisation_id=driver.organisation_id,
        driver_id=driver.id,
        vehicle_id=vehicle.id if vehicle else None,
        risk_level=level,
        risk_score=round(combined, 4),
        indicators=indicators,
        explanation=explanation,
        recommendations=recs,
        confidence=confidence,
        model_version=MODEL_VERSION,
        inputs=features,
        limitations=limitations,
    )
    if persist:
        db.add(assessment)
        db.flush()
    return assessment


def assess_fleet(db: Session, organisation_id: int, limit: int = 500) -> list[RiskAssessment]:
    drivers = (
        db.query(Driver)
        .filter(Driver.organisation_id == organisation_id, Driver.status == "active")
        .limit(limit)
        .all()
    )
    return [assess_driver(db, driver) for driver in drivers]
