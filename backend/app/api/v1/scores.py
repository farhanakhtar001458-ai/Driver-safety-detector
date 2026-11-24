"""Driver safety scoring endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import Pagination, get_db, get_organisation, org_filter, require_permission
from app.models import Driver, DriverScore, Organisation, User
from app.schemas.common import Paginated
from app.schemas.safety import DriverScoreOut, ScoreConfigOut
from app.services.ai import scoring
from app.services.audit import log_action

router = APIRouter(prefix="/scores", tags=["Safety Scores"])


def _latest_weekly_scores(db: Session, org_id: Optional[int]) -> list[DriverScore]:
    query = db.query(DriverScore).filter(
        DriverScore.period == "weekly",
        DriverScore.period_start >= datetime.utcnow() - timedelta(days=14),
    )
    if org_id:
        query = query.filter(DriverScore.organisation_id == org_id)
    scores = query.order_by(DriverScore.period_start.desc()).all()
    seen: set[int] = set()
    latest: list[DriverScore] = []
    for score in scores:
        if score.driver_id in seen:
            continue
        seen.add(score.driver_id)
        latest.append(score)
    return latest


@router.get("/leaderboard", response_model=list[DriverScoreOut])
def leaderboard(
    days: int = Query(default=14, ge=1, le=90),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("scores:read")),
    db: Session = Depends(get_db),
):
    effective_org = organisation_id if user.role == "super_admin" else user.organisation_id
    scores = _latest_weekly_scores(db, effective_org)
    rows = []
    for score in scores:
        driver = db.get(Driver, score.driver_id)
        item = DriverScoreOut.model_validate(score)
        item.driver_name = driver.full_name if driver else "Unknown"
        rows.append(item)
    rows.sort(key=lambda item: item.overall_score, reverse=True)
    return rows[:20]


@router.get("/config", response_model=ScoreConfigOut)
def get_score_config(
    organisation: Organisation = Depends(get_organisation),
    _user: User = Depends(require_permission("scores:read")),
):
    return ScoreConfigOut(
        weights=scoring.get_weights(organisation),
        min_distance_km=10,
        description=(
            "Overall score is a weighted average of category scores. Categories without sensor data are excluded "
            "and remaining weights renormalised. Scores describe recorded behaviour, not crash probability."
        ),
    )


@router.put("/config", response_model=ScoreConfigOut)
def update_score_config(
    payload: dict,
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    user: User = Depends(require_permission("scores:configure")),
    db: Session = Depends(get_db),
):
    weights = payload.get("weights")
    if not isinstance(weights, dict):
        raise HTTPException(status_code=422, detail="weights must be an object of category: number")
    cleaned = {}
    for key, value in weights.items():
        if key not in scoring.DEFAULT_WEIGHTS:
            raise HTTPException(status_code=422, detail=f"Unknown score category '{key}'")
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"Weight for '{key}' must be numeric")
        if numeric < 0 or numeric > 1:
            raise HTTPException(status_code=422, detail=f"Weight for '{key}' must be between 0 and 1")
        cleaned[key] = numeric
    if not cleaned or sum(cleaned.values()) <= 0:
        raise HTTPException(status_code=422, detail="At least one positive weight is required")

    settings = dict(organisation.settings_json or {})
    settings["score_weights"] = cleaned
    organisation.settings_json = settings
    db.flush()
    log_action(
        db,
        user=user,
        action="score.config.update",
        resource_type="organisation",
        resource_id=organisation.id,
        detail={"weights": cleaned},
        request=request,
    )
    return ScoreConfigOut(
        weights=scoring.get_weights(organisation),
        min_distance_km=10,
        description="Weights updated. Changes apply the next time scores are recomputed.",
    )


@router.post("/recompute", response_model=dict)
def recompute_all_scores(
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    user: User = Depends(require_permission("scores:configure")),
    db: Session = Depends(get_db),
):
    drivers = db.query(Driver).filter(Driver.organisation_id == organisation.id, Driver.status == "active").all()
    count = 0
    for driver in drivers:
        scoring.compute_driver_scores(db, driver, organisation)
        count += 1
    log_action(
        db,
        user=user,
        action="score.recompute_all",
        resource_type="organisation",
        resource_id=organisation.id,
        detail={"drivers": count},
        request=request,
    )
    return {"message": f"Recomputed scores for {count} driver(s)", "drivers": count}
