"""Driver management and profile endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.deps import (
    Pagination,
    ensure_org_access,
    get_db,
    get_organisation,
    org_filter,
    require_permission,
)
from app.core.rbac import UserRole
from app.core.security import encrypt_value
from app.models import (
    Driver,
    Organisation,
    DriverScore,
    DrivingEvent,
    Incident,
    RiskAssessment,
    Trip,
    User,
    Vehicle,
)
from app.schemas.common import MessageResponse, Paginated
from app.schemas.fleet import DriverCreate, DriverOut, DriverUpdate, TripOut
from app.schemas.safety import DrivingEventOut, DriverScoreDetail, DriverScoreOut, ScoreHistoryPoint
from app.schemas.saas import CoachingReportOut
from app.services import billing
from app.services.ai import scoring
from app.services.ai.coach import generate_coaching_report
from app.services.audit import log_action
from app.services.serializers import driver_out

router = APIRouter(prefix="/drivers", tags=["Drivers"])


def load_driver(db: Session, user: User, driver_id: int) -> Driver:
    driver = (
        db.query(Driver)
        .options(selectinload(Driver.assigned_vehicles))
        .filter(Driver.id == driver_id)
        .first()
    )
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    ensure_org_access(driver.organisation_id, user)
    return driver


@router.get("", response_model=Paginated[DriverOut])
def list_drivers(
    pagination: Pagination = Depends(),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("drivers:read")),
    db: Session = Depends(get_db),
):
    query = db.query(Driver).options(selectinload(Driver.assigned_vehicles))
    query = org_filter(query, Driver, user, organisation_id)
    if status:
        query = query.filter(Driver.status == status)
    if search:
        needle = f"%{search}%"
        query = query.filter(
            Driver.first_name.ilike(needle) | Driver.last_name.ilike(needle) | Driver.email.ilike(needle)
        )
    total = query.count()
    drivers = query.order_by(Driver.created_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[DriverOut].create(
        [driver_out(driver) for driver in drivers], total, pagination.page, pagination.page_size
    )


@router.post("", response_model=DriverOut, status_code=201)
def create_driver(
    payload: DriverCreate,
    request: Request,
    organisation=Depends(get_organisation),
    user: User = Depends(require_permission("drivers:create")),
    db: Session = Depends(get_db),
):
    if user.role != UserRole.SUPER_ADMIN.value:
        billing.assert_driver_quota(db, organisation)

    linked_user = None
    if payload.user_id:
        linked_user = db.get(User, payload.user_id)
        if not linked_user or (
            user.role != UserRole.SUPER_ADMIN.value and linked_user.organisation_id != organisation.id
        ):
            raise HTTPException(status_code=404, detail="Linked user account not found")

    driver = Driver(
        organisation_id=organisation.id,
        user_id=linked_user.id if linked_user else None,
        employee_id=payload.employee_id,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=payload.email,
        phone_encrypted=encrypt_value(payload.phone) if payload.phone else None,
        licence_number_encrypted=encrypt_value(payload.licence_number) if payload.licence_number else None,
        licence_class=payload.licence_class,
        licence_expiry=payload.licence_expiry,
        licence_issued=payload.licence_issued,
        date_of_birth=payload.date_of_birth,
        hire_date=payload.hire_date,
        address=payload.address,
        city=payload.city,
        emergency_contact_name=payload.emergency_contact_name,
        emergency_contact_phone_encrypted=encrypt_value(payload.emergency_contact_phone)
        if payload.emergency_contact_phone
        else None,
        status=payload.status,
        years_experience=payload.years_experience,
        training_hours=payload.training_hours,
    )
    db.add(driver)
    db.flush()
    log_action(
        db,
        user=user,
        action="driver.create",
        resource_type="driver",
        resource_id=driver.id,
        detail={"name": driver.full_name, "licence_class": driver.licence_class},
        request=request,
    )
    return driver_out(driver)


@router.get("/meta/licences-expiring")
def licences_expiring(
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(require_permission("drivers:read")),
    db: Session = Depends(get_db),
):
    query = db.query(Driver).filter(Driver.licence_expiry.isnot(None))
    query = org_filter(query, Driver, user)
    cutoff = datetime.utcnow().date() + timedelta(days=days)
    rows = query.all()
    expiring = [
        {
            "driver_id": row.id,
            "name": row.full_name,
            "licence_expiry": row.licence_expiry.isoformat(),
            "days_left": (row.licence_expiry - datetime.utcnow().date()).days,
            "status": row.status,
        }
        for row in rows
        if row.licence_expiry and row.licence_expiry <= cutoff
    ]
    expiring.sort(key=lambda item: item["days_left"])
    return {"days": days, "count": len(expiring), "drivers": expiring}


@router.get("/{driver_id}", response_model=DriverOut)
def get_driver(driver_id: int, user: User = Depends(require_permission("drivers:read")), db: Session = Depends(get_db)):
    return driver_out(load_driver(db, user, driver_id))


@router.patch("/{driver_id}", response_model=DriverOut)
def update_driver(
    driver_id: int,
    payload: DriverUpdate,
    request: Request,
    user: User = Depends(require_permission("drivers:update")),
    db: Session = Depends(get_db),
):
    driver = load_driver(db, user, driver_id)
    data = payload.model_dump(exclude_unset=True)
    if "user_id" in data:
        if data["user_id"]:
            linked = db.get(User, data["user_id"])
            if not linked or (
                user.role != UserRole.SUPER_ADMIN.value and linked.organisation_id != driver.organisation_id
            ):
                raise HTTPException(status_code=404, detail="Linked user account not found")
        driver.user_id = data["user_id"]
    if "phone" in data:
        driver.phone_encrypted = encrypt_value(data["phone"]) if data["phone"] else None
    if "licence_number" in data:
        driver.licence_number_encrypted = encrypt_value(data["licence_number"]) if data["licence_number"] else None
    if "emergency_contact_phone" in data:
        driver.emergency_contact_phone_encrypted = (
            encrypt_value(data["emergency_contact_phone"]) if data["emergency_contact_phone"] else None
        )
    for field in (
        "first_name", "last_name", "email", "employee_id", "licence_class", "licence_expiry",
        "licence_issued", "date_of_birth", "hire_date", "address", "city", "emergency_contact_name",
        "status", "years_experience", "training_hours",
    ):
        if field in data and data[field] is not None:
            setattr(driver, field, data[field])
    db.flush()
    log_action(
        db,
        user=user,
        action="driver.update",
        resource_type="driver",
        resource_id=driver.id,
        detail={"fields": sorted(data.keys())},
        request=request,
    )
    return driver_out(driver)


@router.delete("/{driver_id}", response_model=MessageResponse)
def deactivate_driver(
    driver_id: int,
    request: Request,
    user: User = Depends(require_permission("drivers:delete")),
    db: Session = Depends(get_db),
):
    driver = load_driver(db, user, driver_id)
    driver.status = "inactive"
    for vehicle in db.query(Vehicle).filter(Vehicle.assigned_driver_id == driver.id).all():
        vehicle.assigned_driver_id = None
    db.flush()
    log_action(
        db,
        user=user,
        action="driver.deactivate",
        resource_type="driver",
        resource_id=driver.id,
        request=request,
    )
    return MessageResponse(message="Driver deactivated and unassigned from vehicles")


@router.get("/{driver_id}/profile")
def driver_profile(driver_id: int, user: User = Depends(require_permission("drivers:read")), db: Session = Depends(get_db)):
    driver = load_driver(db, user, driver_id)
    scores = (
        db.query(DriverScore)
        .filter(DriverScore.driver_id == driver.id)
        .order_by(DriverScore.period_start.desc())
        .limit(8)
        .all()
    )
    latest = scores[0] if scores else None
    previous = scores[1] if len(scores) > 1 else None
    risk = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.driver_id == driver.id)
        .order_by(RiskAssessment.created_at.desc())
        .first()
    )
    events_30 = (
        db.query(func.count(DrivingEvent.id))
        .filter(
            DrivingEvent.driver_id == driver.id,
            DrivingEvent.occurred_at >= datetime.utcnow() - timedelta(days=30),
        )
        .scalar()
        or 0
    )
    incidents = (
        db.query(func.count(Incident.id))
        .filter(Incident.driver_id == driver.id, Incident.status != "false_alert")
        .scalar()
        or 0
    )
    distance = (
        db.query(func.coalesce(func.sum(Trip.distance_km), 0.0)).filter(Trip.driver_id == driver.id).scalar() or 0.0
    )
    vehicles = db.query(Vehicle).filter(Vehicle.assigned_driver_id == driver.id, Vehicle.is_archived.is_(False)).all()
    return {
        "driver": driver_out(driver).model_dump(),
        "latest_score": DriverScoreOut.model_validate(latest).model_dump() if latest else None,
        "previous_score": previous.overall_score if previous else None,
        "improvement_pct": (
            round((latest.overall_score - previous.overall_score) / max(previous.overall_score, 1) * 100, 1)
            if latest and previous
            else None
        ),
        "risk": {
            "level": risk.risk_level if risk else "not_assessed",
            "score": round(risk.risk_score, 3) if risk else None,
            "explanation": risk.explanation if risk else None,
        },
        "events_30d": int(events_30),
        "incidents_total": int(incidents),
        "distance_km": round(float(distance), 1),
        "vehicles": [
            {"id": v.id, "registration_number": v.registration_number, "status": v.status, "model": f"{v.manufacturer} {v.model}"}
            for v in vehicles
        ],
        "score_history": [
            {"period": s.period, "period_start": s.period_start.isoformat() + "Z", "score": s.overall_score}
            for s in scores
        ],
        "disclaimer": scoring.DISCLAIMER,
    }


@router.get("/{driver_id}/scores", response_model=DriverScoreDetail)
def driver_scores(driver_id: int, user: User = Depends(require_permission("scores:read")), db: Session = Depends(get_db)):
    driver = load_driver(db, user, driver_id)

    def latest(period: str) -> Optional[DriverScore]:
        return (
            db.query(DriverScore)
            .filter(DriverScore.driver_id == driver.id, DriverScore.period == period)
            .order_by(DriverScore.period_start.desc())
            .first()
        )

    weekly = latest("weekly")
    monthly = latest("monthly")
    overall = latest("overall")
    history = (
        db.query(DriverScore)
        .filter(DriverScore.driver_id == driver.id, DriverScore.period == "weekly")
        .order_by(DriverScore.period_start.asc())
        .limit(12)
        .all()
    )
    previous_week = (
        db.query(DriverScore)
        .filter(DriverScore.driver_id == driver.id, DriverScore.period == "weekly")
        .order_by(DriverScore.period_start.desc())
        .offset(1)
        .first()
    )
    improvement = None
    if weekly and previous_week:
        improvement = round(weekly.overall_score - previous_week.overall_score, 1)
    breakdown = weekly.breakdown or {} if weekly else {}
    return DriverScoreDetail(
        driver=driver_out(driver).model_dump(),
        latest=DriverScoreOut.model_validate(weekly) if weekly else None,
        weekly=DriverScoreOut.model_validate(weekly) if weekly else None,
        monthly=DriverScoreOut.model_validate(monthly) if monthly else None,
        history=[
            ScoreHistoryPoint(period_start=score.period_start, overall_score=score.overall_score, period=score.period)
            for score in history
        ],
        improvement_pct=improvement,
        recommendations=scoring.recommendations_for(weekly) if weekly else ["Complete more trips to generate a score."],
        data_coverage={
            "distance_km": weekly.distance_km if weekly else 0,
            "events": weekly.events_count if weekly else 0,
            "confidence": weekly.confidence if weekly else 0,
            "excluded_categories": breakdown.get("excluded_categories", []),
            "simulated": weekly is not None and weekly.breakdown.get("source") == "demo_seed",
        },
        disclaimer=scoring.DISCLAIMER,
    )


@router.post("/{driver_id}/scores/recompute", response_model=DriverScoreOut)
def recompute_scores(
    driver_id: int,
    request: Request,
    user: User = Depends(require_permission("scores:read")),
    db: Session = Depends(get_db),
):
    driver = load_driver(db, user, driver_id)
    organisation = db.get(Organisation, driver.organisation_id)
    scores = scoring.compute_driver_scores(db, driver, organisation)
    log_action(
        db,
        user=user,
        action="score.recompute",
        resource_type="driver",
        resource_id=driver.id,
        request=request,
    )
    score = scores["weekly"]
    result = DriverScoreOut.model_validate(score)
    result.driver_name = driver.full_name
    return result


@router.get("/{driver_id}/events", response_model=Paginated[DrivingEventOut])
def driver_events(
    driver_id: int,
    pagination: Pagination = Depends(),
    severity: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    user: User = Depends(require_permission("behaviour:read")),
    db: Session = Depends(get_db),
):
    driver = load_driver(db, user, driver_id)
    query = db.query(DrivingEvent).filter(DrivingEvent.driver_id == driver.id)
    if severity:
        query = query.filter(DrivingEvent.severity == severity)
    if event_type:
        query = query.filter(DrivingEvent.event_type == event_type)
    total = query.count()
    events = query.order_by(DrivingEvent.occurred_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    items = []
    for event in events:
        vehicle = db.get(Vehicle, event.vehicle_id)
        item = DrivingEventOut.model_validate(event)
        item.registration_number = vehicle.registration_number if vehicle else None
        item.driver_name = driver.full_name
        items.append(item)
    return Paginated[DrivingEventOut].create(items, total, pagination.page, pagination.page_size)


@router.get("/{driver_id}/trips", response_model=Paginated[TripOut])
def driver_trips(
    driver_id: int,
    pagination: Pagination = Depends(),
    user: User = Depends(require_permission("tracking:read")),
    db: Session = Depends(get_db),
):
    driver = load_driver(db, user, driver_id)
    query = db.query(Trip).filter(Trip.driver_id == driver.id)
    total = query.count()
    trips = query.order_by(Trip.start_time.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    items = []
    for trip in trips:
        item = TripOut.model_validate(trip)
        item.driver_name = driver.full_name
        items.append(item)
    return Paginated[TripOut].create(items, total, pagination.page, pagination.page_size)


@router.post("/{driver_id}/coaching-report", response_model=CoachingReportOut)
def coaching_report(
    driver_id: int,
    request: Request,
    days: int = Query(default=30, ge=7, le=90),
    user: User = Depends(require_permission("assistant:use")),
    db: Session = Depends(get_db),
):
    driver = load_driver(db, user, driver_id)
    report = generate_coaching_report(db, driver.id, days)
    log_action(
        db,
        user=user,
        action="coaching.report",
        resource_type="driver",
        resource_id=driver.id,
        request=request,
    )
    return CoachingReportOut(**report)
