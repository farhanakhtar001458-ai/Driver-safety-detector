"""Road safety intelligence: hotspots, live hazards and route analysis.

Historical hotspot data is labelled by provenance. The demo rows are explicitly
illustrative and are never presented as official accident statistics.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db, org_filter, require_permission
from app.models import RoadHazard, RoadHotspot, User
from app.schemas.common import MessageResponse
from app.schemas.safety import RoadHazardIn, RoadHazardOut, RouteAnalysisRequest, RouteAnalysisResponse
from app.services.ai.rules_engine import haversine_km
from app.services.audit import log_action

router = APIRouter(prefix="/intelligence", tags=["Road Safety Intelligence"])


@router.get("/hotspots")
def hotspots(
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("road_safety:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(RoadHotspot), RoadHotspot, user, organisation_id)
    rows = query.all()
    return {
        "hotspots": [
            {
                "id": row.id,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "label": row.label,
                "severity": row.severity,
                "radius_meters": row.radius_meters,
                "historical_count": row.historical_count,
                "source": row.source_name,
                "is_illustrative": row.is_illustrative,
            }
            for row in rows
        ],
        "disclaimer": (
            "Hotspot data in this demo is illustrative and does not represent official road accident statistics. "
            "Replace it with a verified government or municipal dataset before operational use."
        ),
        "data_sources": sorted({row.source_name for row in rows}),
    }


@router.get("/hazards", response_model=list[RoadHazardOut])
def hazards(
    status: Optional[str] = Query(default="active"),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("road_safety:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(RoadHazard), RoadHazard, user, organisation_id)
    if status:
        query = query.filter(RoadHazard.status == status)
    return [RoadHazardOut.model_validate(row) for row in query.order_by(RoadHazard.created_at.desc()).all()]


@router.post("/hazards", response_model=RoadHazardOut, status_code=201)
def report_hazard(
    payload: RoadHazardIn,
    request: Request,
    user: User = Depends(require_permission("road_safety:report")),
    db: Session = Depends(get_db),
):
    if not user.organisation_id:
        raise HTTPException(status_code=400, detail="Hazard reporting requires an organisation account")
    hazard = RoadHazard(
        organisation_id=user.organisation_id,
        reported_by_id=user.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        hazard_type=payload.hazard_type,
        severity=payload.severity,
        description=payload.description,
        expires_at=datetime.utcnow() + timedelta(hours=payload.expires_in_hours),
        is_simulated=False,
    )
    db.add(hazard)
    db.flush()
    log_action(
        db,
        user=user,
        action="road_hazard.create",
        resource_type="road_hazard",
        resource_id=hazard.id,
        detail={"type": hazard.hazard_type, "severity": hazard.severity},
        request=request,
    )
    return RoadHazardOut.model_validate(hazard)


@router.patch("/hazards/{hazard_id}", response_model=RoadHazardOut)
def update_hazard(
    hazard_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_permission("road_safety:report")),
    db: Session = Depends(get_db),
):
    hazard = db.get(RoadHazard, hazard_id)
    if not hazard:
        raise HTTPException(status_code=404, detail="Hazard not found")
    from app.core.deps import ensure_org_access

    ensure_org_access(hazard.organisation_id, user)
    if payload.get("status") in {"active", "cleared", "expired"}:
        hazard.status = payload["status"]
    if payload.get("severity"):
        hazard.severity = payload["severity"]
    if payload.get("description"):
        hazard.description = payload["description"]
    db.flush()
    log_action(db, user=user, action="road_hazard.update", resource_type="road_hazard", resource_id=hazard.id, request=request)
    return RoadHazardOut.model_validate(hazard)


@router.post("/route-analysis", response_model=RouteAnalysisResponse)
def route_analysis(
    payload: RouteAnalysisRequest,
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("road_safety:read")),
    db: Session = Depends(get_db),
):
    effective_org = organisation_id if user.role == "super_admin" else user.organisation_id
    points = [(float(point["latitude"]), float(point["longitude"])) for point in payload.points]
    distance = 0.0
    for index in range(1, len(points)):
        distance += haversine_km(*points[index - 1], *points[index])

    hazards_query = db.query(RoadHazard).filter(RoadHazard.status == "active")
    hotspots_query = db.query(RoadHotspot)
    if effective_org:
        hazards_query = hazards_query.filter(RoadHazard.organisation_id == effective_org)
        hotspots_query = hotspots_query.filter(
            (RoadHotspot.organisation_id == effective_org) | (RoadHotspot.organisation_id.is_(None))
        )
    hazards = hazards_query.all()
    hotspots = hotspots_query.all()

    def near(lat: float, lng: float, radius_km: float) -> bool:
        for point in points:
            if haversine_km(point[0], point[1], lat, lng) <= radius_km:
                return True
        return False

    route_hazards = [h for h in hazards if near(h.latitude, h.longitude, 5.0)]
    route_hotspots = [h for h in hotspots if near(h.latitude, h.longitude, 3.5)]
    severity_score = sum(
        {"low": 1, "medium": 2, "high": 3}.get(h.severity, 1) for h in route_hazards
    ) + sum({"low": 1, "medium": 2, "high": 3}.get(h.severity, 1) for h in route_hotspots)

    risk_score = round(min(100, severity_score / max(1, len(points)) * 25), 1)
    if risk_score >= 60:
        rating = "high"
    elif risk_score >= 30:
        rating = "moderate"
    else:
        rating = "low"

    warnings = []
    for hazard in route_hazards[:5]:
        warnings.append(f"{hazard.hazard_type.replace('_', ' ').title()}: {hazard.description or 'No description'}")
    recommendations = []
    if route_hazards:
        recommendations.append("Allow extra journey time and reduce speed near the reported hazards.")
    if any(h.hazard_type in {"fog", "flooding"} for h in route_hazards):
        recommendations.append("Check visibility and road closure updates before departure.")
    if not warnings:
        recommendations.append("No active hazards reported near this route. Continue routine checks.")

    return RouteAnalysisResponse(
        distance_km=round(distance, 2),
        risk_rating=rating,
        risk_score=risk_score,
        hazard_count=len(route_hazards),
        hotspot_count=len(route_hotspots),
        warnings=warnings,
        recommendations=recommendations,
        data_sources=["reported road hazards", "historical hotspot reference data (illustrative in demo)"],
        disclaimer=(
            "Route analysis uses reported hazards and illustrative hotspot data. It does not use live traffic "
            "or official accident statistics in this demo."
        ),
    )


@router.get("/weather")
def weather(
    latitude: float = Query(default=23.2599, ge=-90, le=90),
    longitude: float = Query(default=77.4126, ge=-180, le=180),
    user: User = Depends(require_permission("road_safety:read")),
):
    """Weather context.

    No weather provider is configured by default, so this returns a clearly
    labelled simulated sample rather than fabricated live conditions.
    """
    from app.core.config import settings as app_settings

    configured = bool(getattr(app_settings, "WEATHER_API_KEY", ""))
    return {
        "location": {"latitude": latitude, "longitude": longitude},
        "simulated": not configured,
        "source": "openweathermap" if configured else "simulated demo sample",
        "observed_at": datetime.utcnow().isoformat() + "Z",
        "condition": "Haze" if not configured else "Unavailable",
        "temperature_c": 31.0 if not configured else None,
        "visibility_km": 2.5 if not configured else None,
        "wind_kph": 12.0 if not configured else None,
        "driving_advice": [
            "Reduce speed in low visibility and use low-beam headlights.",
            "Increase following distance in haze or rain.",
            "Check live conditions with an official weather service before departure.",
        ],
        "disclaimer": (
            "This demo does not call a live weather API. Values are illustrative and must not be used for "
            "operational decisions."
            if not configured
            else "Weather data is provided by the configured provider."
        ),
    }


@router.get("/overview")
def intelligence_overview(
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("road_safety:read")),
    db: Session = Depends(get_db),
):
    hazard_query = org_filter(db.query(RoadHazard), RoadHazard, user, organisation_id).filter(
        RoadHazard.status == "active"
    )
    hotspot_query = org_filter(db.query(RoadHotspot), RoadHotspot, user, organisation_id)
    hazards = hazard_query.all()
    hotspots = hotspot_query.all()
    return {
        "active_hazards": len(hazards),
        "hotspots": len(hotspots),
        "high_severity_hazards": sum(1 for h in hazards if h.severity == "high"),
        "illustrative_hotspots": sum(1 for h in hotspots if h.is_illustrative),
        "by_type": _count_by(hazards, "hazard_type"),
        "disclaimer": "Hotspot data is illustrative in this demo and is not official accident statistics.",
    }


def _count_by(rows, field: str) -> list[dict]:
    counts: dict[str, int] = {}
    for row in rows:
        value = getattr(row, field)
        counts[value] = counts.get(value, 0) + 1
    return [{"type": key, "count": value} for key, value in sorted(counts.items(), key=lambda kv: -kv[1])]
