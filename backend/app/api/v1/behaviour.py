"""Driving behaviour analytics, patterns and configuration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import Pagination, get_db, get_organisation, org_filter, require_permission
from app.models import Driver, DriverScore, DrivingEvent, Organisation, Trip, User, Vehicle
from app.schemas.common import MessageResponse, Paginated
from app.schemas.safety import (
    BehaviourSummary,
    DrivingEventOut,
    EventCreate,
    PatternInsight,
    PatternResponse,
)
from app.services.ai import rules_engine
from app.services.audit import log_action

router = APIRouter(prefix="/behaviour", tags=["Driving Behaviour"])


def _decorate(event: DrivingEvent, db: Session, driver: Optional[Driver] = None, vehicle: Optional[Vehicle] = None) -> DrivingEventOut:
    item = DrivingEventOut.model_validate(event)
    vehicle = vehicle or (db.get(Vehicle, event.vehicle_id) if event.vehicle_id else None)
    driver = driver or (db.get(Driver, event.driver_id) if event.driver_id else None)
    item.registration_number = vehicle.registration_number if vehicle else None
    item.driver_name = driver.full_name if driver else None
    return item


@router.get("/events", response_model=Paginated[DrivingEventOut])
def list_events(
    pagination: Pagination = Depends(),
    event_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    driver_id: Optional[int] = Query(default=None),
    vehicle_id: Optional[int] = Query(default=None),
    from_time: Optional[datetime] = Query(default=None, alias="from"),
    to_time: Optional[datetime] = Query(default=None, alias="to"),
    simulated: Optional[bool] = Query(default=None),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("behaviour:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(DrivingEvent), DrivingEvent, user, organisation_id)
    if event_type:
        query = query.filter(DrivingEvent.event_type == event_type)
    if severity:
        query = query.filter(DrivingEvent.severity == severity)
    if driver_id:
        query = query.filter(DrivingEvent.driver_id == driver_id)
    if vehicle_id:
        query = query.filter(DrivingEvent.vehicle_id == vehicle_id)
    if from_time:
        query = query.filter(DrivingEvent.occurred_at >= from_time)
    if to_time:
        query = query.filter(DrivingEvent.occurred_at <= to_time)
    if simulated is not None:
        query = query.filter(DrivingEvent.is_simulated.is_(simulated))
    total = query.count()
    events = query.order_by(DrivingEvent.occurred_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[DrivingEventOut].create(
        [_decorate(event, db) for event in events], total, pagination.page, pagination.page_size
    )


@router.get("/events/{event_id}", response_model=DrivingEventOut)
def get_event(
    event_id: int,
    user: User = Depends(require_permission("behaviour:read")),
    db: Session = Depends(get_db),
):
    event = db.get(DrivingEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    from app.core.deps import ensure_org_access

    ensure_org_access(event.organisation_id, user)
    return _decorate(event, db)


@router.post("/events", response_model=DrivingEventOut, status_code=201)
def report_event(
    payload: EventCreate,
    request: Request,
    user: User = Depends(require_permission("incidents:create")),
    db: Session = Depends(get_db),
):
    """Allow a safety officer to record an observed event (e.g. from a camera review)."""
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    from app.core.deps import ensure_org_access

    ensure_org_access(vehicle.organisation_id, user)
    event = DrivingEvent(
        organisation_id=vehicle.organisation_id,
        vehicle_id=vehicle.id,
        driver_id=payload.driver_id or vehicle.assigned_driver_id,
        event_type=payload.event_type,
        severity=payload.severity,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed_kph=payload.speed_kph,
        speed_limit_kph=payload.speed_limit_kph,
        sensor_data={"reported_by": user.email, "description": payload.description, "verified": True},
        recommended_action=rules_engine.RECOMMENDED_ACTIONS.get(payload.event_type),
        is_simulated=False,
        source="manual",
        occurred_at=payload.occurred_at or datetime.utcnow(),
    )
    db.add(event)
    db.flush()
    log_action(
        db,
        user=user,
        action="event.report",
        resource_type="driving_event",
        resource_id=event.id,
        detail={"event_type": event.event_type, "severity": event.severity},
        request=request,
    )
    return _decorate(event, db)


@router.get("/summary", response_model=BehaviourSummary)
def behaviour_summary(
    days: int = Query(default=30, ge=1, le=365),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("behaviour:read")),
    db: Session = Depends(get_db),
):
    effective_org = organisation_id if user.role == "super_admin" else user.organisation_id
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(DrivingEvent).filter(DrivingEvent.occurred_at >= since)
    if effective_org:
        query = query.filter(DrivingEvent.organisation_id == effective_org)
    events = query.all()

    by_type: dict[str, int] = {}
    by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    by_driver: dict[int, dict] = {}
    for event in events:
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
        by_severity[event.severity] = by_severity.get(event.severity, 0) + 1
        if event.driver_id:
            entry = by_driver.setdefault(event.driver_id, {"driver_id": event.driver_id, "events": 0, "high_risk": 0})
            entry["events"] += 1
            if event.severity in {"high", "critical"}:
                entry["high_risk"] += 1

    driver_ids = list(by_driver.keys())
    drivers = {d.id: d for d in db.query(Driver).filter(Driver.id.in_(driver_ids)).all()} if driver_ids else {}
    for driver_id, entry in by_driver.items():
        driver = drivers.get(driver_id)
        entry["driver_name"] = driver.full_name if driver else f"Driver {driver_id}"

    top = sorted(by_driver.values(), key=lambda item: item["events"], reverse=True)[:5]

    distance_query = db.query(func.coalesce(func.sum(Trip.distance_km), 0.0)).filter(Trip.start_time >= since)
    if effective_org:
        distance_query = distance_query.filter(Trip.organisation_id == effective_org)
    distance = float(distance_query.scalar() or 0.0)
    simulated = sum(1 for event in events if event.is_simulated)
    return BehaviourSummary(
        period_days=days,
        total_events=len(events),
        high_risk_events=sum(1 for event in events if event.severity in {"high", "critical"}),
        critical_events=by_severity["critical"],
        events_per_100km=round(len(events) / max(distance, 10) * 100, 2),
        distance_km=round(distance, 1),
        by_type=[{"event_type": key, "count": value} for key, value in sorted(by_type.items(), key=lambda kv: -kv[1])],
        by_severity=[{"severity": key, "count": value} for key, value in by_severity.items()],
        trend=rules_engine.score_trend(db, effective_org) if effective_org else [],
        top_drivers=top,
        safest_drivers=_safest_drivers(db, effective_org),
        simulation_share_pct=round(simulated / len(events) * 100, 1) if events else 0.0,
    )


def _safest_drivers(db: Session, org_id: Optional[int]) -> list[dict]:
    if not org_id:
        return []
    scores = (
        db.query(DriverScore)
        .filter(
            DriverScore.organisation_id == org_id,
            DriverScore.period == "weekly",
            DriverScore.period_start >= datetime.utcnow() - timedelta(days=14),
        )
        .order_by(DriverScore.period_start.desc())
        .all()
    )
    seen: set[int] = set()
    rows = []
    for score in scores:
        if score.driver_id in seen:
            continue
        seen.add(score.driver_id)
        driver = db.get(Driver, score.driver_id)
        rows.append(
            {
                "driver_id": score.driver_id,
                "driver_name": driver.full_name if driver else "Unknown",
                "score": score.overall_score,
            }
        )
    rows.sort(key=lambda item: item["score"], reverse=True)
    return rows[:5]


@router.get("/patterns", response_model=PatternResponse)
def behaviour_patterns(
    days: int = Query(default=30, ge=7, le=180),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("behaviour:read")),
    db: Session = Depends(get_db),
):
    effective_org = organisation_id if user.role == "super_admin" else user.organisation_id
    if not effective_org:
        raise HTTPException(status_code=400, detail="organisation_id is required for super administrators")
    patterns = rules_engine.analyse_patterns(db, effective_org, days)
    return PatternResponse(
        generated_at=datetime.utcnow(),
        period_days=days,
        patterns=[PatternInsight(**pattern) for pattern in patterns],
        methodology=(
            "Patterns are descriptive aggregates of recorded events: event counts, distinct days, time-of-day "
            "distribution and per-vehicle concentration. Thresholds are explicit and auditable. No pattern is a "
            "prediction of future behaviour."
        ),
        limitations=[
            "Simulated telemetry is included and labelled; patterns may reflect the simulator rather than real driving.",
            "Event detection depends on GPS sample rate and configured thresholds.",
            "Camera-derived observations are low-confidence until verified.",
        ],
    )


@router.get("/config")
def get_behaviour_config(
    organisation: Organisation = Depends(get_organisation),
    _user: User = Depends(require_permission("behaviour:read")),
):
    thresholds = rules_engine.get_thresholds(organisation)
    return {
        "thresholds": thresholds,
        "defaults": rules_engine.DEFAULT_THRESHOLDS,
        "speed_limits": rules_engine.SPEED_LIMITS_BY_TYPE,
        "note": "Thresholds are organisation-wide and auditable. Changes apply to newly detected events only.",
    }


@router.put("/config")
def update_behaviour_config(
    payload: dict,
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    user: User = Depends(require_permission("behaviour:configure")),
    db: Session = Depends(get_db),
):
    allowed = set(rules_engine.DEFAULT_THRESHOLDS.keys())
    current = dict(organisation.settings_json or {})
    behaviour = dict(current.get("behaviour", {}))
    updates = {}
    for key, value in payload.items():
        if key not in allowed:
            raise HTTPException(status_code=422, detail=f"Unknown threshold '{key}'")
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"Threshold '{key}' must be numeric")
        if numeric <= 0 or numeric > 200:
            raise HTTPException(status_code=422, detail=f"Threshold '{key}' is out of range")
        behaviour[key] = numeric
        updates[key] = numeric
    current["behaviour"] = behaviour
    organisation.settings_json = current
    db.flush()
    log_action(
        db,
        user=user,
        action="behaviour.config.update",
        resource_type="organisation",
        resource_id=organisation.id,
        detail={"updates": updates},
        request=request,
    )
    return {"message": "Thresholds updated", "thresholds": rules_engine.get_thresholds(organisation)}
