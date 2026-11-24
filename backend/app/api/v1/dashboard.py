"""Main dashboard aggregation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, org_filter, require_permission
from app.models import Driver, DriverScore, User, Vehicle
from app.services.dashboard import dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("")
def dashboard(
    days: int = Query(default=30, ge=1, le=365),
    organisation_id: int | None = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("dashboard:read")),
    db: Session = Depends(get_db),
):
    effective_org = organisation_id if user.role == "super_admin" else user.organisation_id
    if not effective_org:
        return {
            "generated_at": None,
            "message": "Super administrators must select an organisation to view a dashboard.",
            "kpis": {},
            "trend": [],
            "events_by_type": [],
            "events_by_severity": [],
            "vehicle_activity": [],
            "leaderboard": [],
            "vehicle_health": [],
            "recent_incidents": [],
            "recent_notifications": [],
            "disclaimer": "Select an organisation to load its dashboard.",
        }
    return dashboard_summary(db, effective_org, days=days, user=user)


@router.get("/activity")
def fleet_activity(
    days: int = Query(default=14, ge=1, le=90),
    organisation_id: int | None = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("dashboard:read")),
    db: Session = Depends(get_db),
):
    from app.services.dashboard import _daily_activity

    effective_org = organisation_id if user.role == "super_admin" else user.organisation_id
    if not effective_org:
        return {"activity": []}
    return {"activity": _daily_activity(db, effective_org, days)}


@router.get("/quick-stats")
def quick_stats(
    organisation_id: int | None = Query(default=None, alias="organisation_id"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lightweight payload for the sidebar/topbar."""
    vehicle_query = db.query(Vehicle).filter(Vehicle.is_archived.is_(False))
    driver_query = db.query(Driver)
    if user.role == "super_admin":
        if organisation_id:
            vehicle_query = vehicle_query.filter(Vehicle.organisation_id == organisation_id)
            driver_query = driver_query.filter(Driver.organisation_id == organisation_id)
    else:
        vehicle_query = vehicle_query.filter(Vehicle.organisation_id == user.organisation_id)
        driver_query = driver_query.filter(Driver.organisation_id == user.organisation_id)
    return {
        "vehicles": vehicle_query.count(),
        "drivers": driver_query.count(),
        "active_vehicles": vehicle_query.filter(Vehicle.status == "active").count(),
    }
