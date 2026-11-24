"""AI risk assessment endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import Pagination, get_db, get_organisation, org_filter, require_permission
from app.models import Driver, Organisation, RiskAssessment, User, Vehicle
from app.schemas.common import Paginated
from app.schemas.safety import (
    RiskAssessmentOut,
    RiskAssessRequest,
    RiskModelInfo,
    RiskOverview,
)
from app.services.ai import risk_model
from app.services.audit import log_action

router = APIRouter(prefix="/risk", tags=["AI Risk Analysis"])


def _out(assessment: RiskAssessment, db: Session) -> RiskAssessmentOut:
    driver = db.get(Driver, assessment.driver_id) if assessment.driver_id else None
    vehicle = db.get(Vehicle, assessment.vehicle_id) if assessment.vehicle_id else None
    item = RiskAssessmentOut.model_validate(assessment)
    item.driver_name = driver.full_name if driver else None
    item.registration_number = vehicle.registration_number if vehicle else None
    return item


@router.get("/model-info", response_model=RiskModelInfo)
def model_info(user: User = Depends(require_permission("risk:read"))):
    info = risk_model.model_info()
    return RiskModelInfo(**info)


@router.get("/overview", response_model=RiskOverview)
def risk_overview(
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("risk:read")),
    db: Session = Depends(get_db),
):
    effective_org = organisation_id if user.role == "super_admin" else user.organisation_id
    query = db.query(RiskAssessment)
    if effective_org:
        query = query.filter(RiskAssessment.organisation_id == effective_org)
    assessments = query.order_by(RiskAssessment.created_at.desc()).all()

    latest: dict[int, RiskAssessment] = {}
    for assessment in assessments:
        if assessment.driver_id and assessment.driver_id not in latest:
            latest[assessment.driver_id] = assessment

    by_level = {"low": 0, "moderate": 0, "high": 0, "critical": 0}
    for assessment in latest.values():
        by_level[assessment.risk_level] = by_level.get(assessment.risk_level, 0) + 1

    high_risk = []
    for assessment in sorted(
        [a for a in latest.values() if a.risk_level in {"high", "critical"}],
        key=lambda item: item.risk_score,
        reverse=True,
    )[:8]:
        driver = db.get(Driver, assessment.driver_id) if assessment.driver_id else None
        high_risk.append(
            {
                "driver_id": assessment.driver_id,
                "driver_name": driver.full_name if driver else "Unknown",
                "risk_level": assessment.risk_level,
                "risk_score": round(assessment.risk_score, 3),
                "confidence": assessment.confidence,
                "top_indicator": (assessment.indicators or [{}])[0].get("label")
                if assessment.indicators
                else None,
                "assessed_at": assessment.created_at.isoformat() + "Z",
            }
        )

    fleet_index = (
        round(sum(a.risk_score for a in latest.values()) / len(latest) * 100, 1) if latest else 0.0
    )
    return RiskOverview(
        generated_at=datetime.utcnow(),
        total_assessed=len(latest),
        by_level=[{"level": level, "count": count} for level, count in by_level.items()],
        high_risk_drivers=high_risk,
        fleet_risk_index=fleet_index,
        model_info=risk_model.model_info(),
        disclaimer=risk_model.DISCLAIMER,
    )


@router.post("/assess", response_model=RiskAssessmentOut, status_code=201)
def assess_driver(
    payload: RiskAssessRequest,
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    user: User = Depends(require_permission("risk:assess")),
    db: Session = Depends(get_db),
):
    driver = db.get(Driver, payload.driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    if user.role != "super_admin" and driver.organisation_id != organisation.id:
        raise HTTPException(status_code=404, detail="Driver not found")
    vehicle = db.get(Vehicle, payload.vehicle_id) if payload.vehicle_id else None
    if payload.vehicle_id and not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    assessment = risk_model.assess_driver(db, driver, vehicle)
    log_action(
        db,
        user=user,
        action="risk.assess",
        resource_type="driver",
        resource_id=driver.id,
        detail={"risk_level": assessment.risk_level, "risk_score": assessment.risk_score},
        request=request,
    )
    return _out(assessment, db)


@router.post("/assess-fleet", response_model=list[RiskAssessmentOut], status_code=201)
def assess_fleet(
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    user: User = Depends(require_permission("risk:assess")),
    db: Session = Depends(get_db),
):
    drivers = (
        db.query(Driver)
        .filter(Driver.organisation_id == organisation.id, Driver.status == "active")
        .limit(200)
        .all()
    )
    results = [risk_model.assess_driver(db, driver) for driver in drivers]
    log_action(
        db,
        user=user,
        action="risk.assess_fleet",
        resource_type="organisation",
        resource_id=organisation.id,
        detail={"drivers": len(results)},
        request=request,
    )
    return [_out(assessment, db) for assessment in results]


@router.get("/assessments", response_model=Paginated[RiskAssessmentOut])
def list_assessments(
    pagination: Pagination = Depends(),
    risk_level: Optional[str] = Query(default=None),
    driver_id: Optional[int] = Query(default=None),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("risk:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(RiskAssessment), RiskAssessment, user, organisation_id)
    if risk_level:
        query = query.filter(RiskAssessment.risk_level == risk_level)
    if driver_id:
        query = query.filter(RiskAssessment.driver_id == driver_id)
    total = query.count()
    rows = query.order_by(RiskAssessment.created_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[RiskAssessmentOut].create(
        [_out(row, db) for row in rows], total, pagination.page, pagination.page_size
    )


@router.get("/assessments/{assessment_id}", response_model=RiskAssessmentOut)
def get_assessment(
    assessment_id: int,
    user: User = Depends(require_permission("risk:read")),
    db: Session = Depends(get_db),
):
    assessment = db.get(RiskAssessment, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Risk assessment not found")
    from app.core.deps import ensure_org_access

    ensure_org_access(assessment.organisation_id, user)
    return _out(assessment, db)
