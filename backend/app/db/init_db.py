"""Database bootstrap: schema creation plus seeding of platform reference data."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import ALL_PERMISSIONS, DEFAULT_PERMISSIONS, ROLE_LABELS, UserRole
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import AIModelVersion, Permission, Role, SubscriptionPlan, role_permissions

logger = logging.getLogger(__name__)

PLANS = [
    {
        "code": "free",
        "name": "Free",
        "description": "For individuals and very small teams evaluating digital safety.",
        "price_monthly": 0,
        "max_vehicles": 2,
        "max_drivers": 2,
        "trial_days": 0,
        "features": ["Basic dashboard", "Basic safety reports", "2 vehicles", "Community support"],
        "sort_order": 0,
    },
    {
        "code": "starter",
        "name": "Starter",
        "description": "GPS monitoring and driver management for growing fleets.",
        "price_monthly": 1499,
        "max_vehicles": 15,
        "max_drivers": 15,
        "trial_days": 14,
        "features": [
            "Everything in Free",
            "Live GPS monitoring",
            "Driver management",
            "Safety analytics",
            "Geofencing",
            "Email notifications",
            "Standard support",
        ],
        "sort_order": 1,
    },
    {
        "code": "professional",
        "name": "Professional",
        "description": "AI risk analysis, predictive maintenance and advanced reporting.",
        "price_monthly": 3499,
        "max_vehicles": 60,
        "max_drivers": 60,
        "trial_days": 14,
        "features": [
            "Everything in Starter",
            "AI risk analysis",
            "Advanced reporting & exports",
            "Predictive maintenance",
            "Automated notifications",
            "AI coaching assistant",
            "Priority support",
        ],
        "sort_order": 2,
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "description": "Contract-based limits, custom integrations and dedicated support.",
        "price_monthly": 0,
        "max_vehicles": 0,  # 0 = unlimited / contract based
        "max_drivers": 0,
        "trial_days": 30,
        "features": [
            "Everything in Professional",
            "Unlimited or contract-based vehicles",
            "Custom integrations & SSO",
            "Advanced administration",
            "Audit log retention controls",
            "Dedicated success manager",
            "SLA & onboarding support",
        ],
        "sort_order": 3,
        "is_custom": True,
    },
]

def _model_versions() -> list[dict]:
    """Build the AI model registry entries.

    Risk-model metrics are read from the trained model itself so the registry can
    never drift from what `/risk/model-info` reports. Only genuinely measured
    values are published - entries for components without a formal evaluation
    describe their validation status instead of inventing accuracy numbers.
    """
    from app.services.ai import risk_model, scoring

    risk_metrics = dict(risk_model.model_info()["metrics"])
    risk_metrics["holdout_rows"] = risk_metrics.get("holdout_rows", 0)

    return [
        {
            "name": "Driver Safety Scoring",
            "version": settings.SCORING_MODEL_VERSION,
            "task": "driver_scoring",
            "status": "active",
            "description": (
                "Explainable weighted scoring across speed, braking, acceleration, cornering, "
                "seatbelt and consistency. Missing categories are excluded and weights renormalised."
            ),
            "metrics": {
                "categories": len(scoring.DEFAULT_WEIGHTS),
                "default_weights": scoring.DEFAULT_WEIGHTS,
                "min_distance_km": 10,
                "formal_evaluation": "not performed - deterministic formula, unit-tested",
            },
            "limitations": [
                "Scores describe observed behaviour, not crash probability.",
                "Seatbelt and distraction categories are only scored where sensor data exists.",
                "No calibrated mapping from score to incident likelihood has been established.",
            ],
        },
        {
            "name": "Fleet Risk Classifier",
            "version": settings.RISK_MODEL_VERSION,
            "task": "risk_classification",
            "status": "active",
            "description": (
                "Gradient-boosted classifier over behavioural, vehicle and exposure features, "
                "combined with transparent safety rules."
            ),
            "metrics": risk_metrics,
            "limitations": [
                "Not an accident prediction service. Outputs are triage priorities.",
                "Calibration degrades when input data coverage is low.",
                "Trained on synthetic historical data for demonstration.",
            ],
        },
        {
            "name": "Event Detection Rules",
            "version": "rules-2.1.0",
            "task": "event_detection",
            "status": "active",
            "description": (
                "Threshold-based detection for speeding, harsh braking, rapid acceleration and "
                "aggressive cornering."
            ),
            "metrics": {
                "rule_count": 7,
                "formal_evaluation": "unit-tested against synthetic traces; no field validation yet",
            },
            "limitations": [
                "Thresholds are configurable per organisation and vary by vehicle type.",
                "GPS sample rate limits which manoeuvres can be detected reliably.",
            ],
        },
        {
            "name": "Coaching Assistant",
            "version": "coach-llm-1.2.0",
            "task": "coaching",
            "status": "active",
            "description": "LLM-assisted coaching grounded in driver telemetry and safety scores.",
            "metrics": {
                "mode": "llm when configured, otherwise local templates",
                "grounding": "retrieved context is echoed in the response",
                "formal_evaluation": "not performed",
            },
            "limitations": [
                "Cannot provide medical, legal or emergency guidance.",
                "Local mode produces template answers, not generative advice.",
            ],
        },
    ]


MODEL_VERSIONS = _model_versions()


def create_schema() -> None:
    Base.metadata.create_all(bind=engine)


def seed_reference_data(db: Session) -> None:
    # Roles & permissions
    for role_enum in UserRole:
        role = db.query(Role).filter(Role.code == role_enum.value).first()
        if not role:
            role = Role(code=role_enum.value, name=ROLE_LABELS[role_enum.value], is_system=True)
            db.add(role)
            db.flush()
        role.name = ROLE_LABELS[role_enum.value]

    for code in ALL_PERMISSIONS:
        permission = db.query(Permission).filter(Permission.code == code).first()
        if not permission:
            db.add(Permission(code=code, description=f"Grants {code.replace(':', ' ')}"))
    db.flush()

    for role_enum in UserRole:
        role = db.query(Role).filter(Role.code == role_enum.value).first()
        if not role:
            continue
        wanted = set(DEFAULT_PERMISSIONS[role_enum])
        if "*" in wanted:
            wanted = set(ALL_PERMISSIONS)
        existing = {p.code for p in role.permissions}
        for code in wanted - existing:
            permission = db.query(Permission).filter(Permission.code == code).first()
            if permission:
                role.permissions.append(permission)
    db.flush()

    # Subscription plans
    for plan_data in PLANS:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == plan_data["code"]).first()
        if not plan:
            db.add(SubscriptionPlan(**plan_data))
    db.flush()

    # AI model registry
    for model_data in MODEL_VERSIONS:
        existing = db.query(AIModelVersion).filter(
            AIModelVersion.version == model_data["version"]
        ).first()
        if not existing:
            db.add(AIModelVersion(**model_data))
    db.commit()


def init_db(seed_demo: bool | None = None) -> None:
    create_schema()
    db = SessionLocal()
    try:
        seed_reference_data(db)
        should_seed = settings.SEED_DEMO_DATA if seed_demo is None else seed_demo
        if should_seed:
            from app.seed import seed_demo_data

            seed_demo_data(db)
    finally:
        db.close()
