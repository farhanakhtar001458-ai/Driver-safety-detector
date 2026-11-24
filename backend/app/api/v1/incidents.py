"""Incident reporting and investigation workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import Pagination, ensure_org_access, get_db, org_filter, require_permission
from app.models import Driver, Incident, User, Vehicle
from app.schemas.common import MessageResponse, Paginated
from app.schemas.safety import IncidentCreate, IncidentOut, IncidentSummary, IncidentUpdate
from app.services.audit import log_action
from app.services.notifications import create_notification
from app.services.serializers import incident_out

router = APIRouter(prefix="/incidents", tags=["Incidents"])

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"under_investigation", "verified", "false_alert"},
    "under_investigation": {"verified", "resolved", "false_alert"},
    "verified": {"resolved", "under_investigation"},
    "resolved": set(),
    "false_alert": set(),
}


def load_incident(db: Session, user: User, incident_id: int) -> Incident:
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    ensure_org_access(incident.organisation_id, user)
    return incident


def _transition(incident: Incident, new_status: str) -> None:
    if new_status == incident.status:
        return
    if new_status not in ALLOWED_TRANSITIONS.get(incident.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move an incident from '{incident.status}' to '{new_status}'",
        )
    incident.status = new_status


def _notify_incident(db: Session, incident: Incident, status_label: str, priority: str = "high") -> None:
    create_notification(
        db,
        organisation_id=incident.organisation_id,
        notification_type="incident_update",
        title=f"Incident {status_label}",
        message=f"{incident.title} (ref #{incident.id})",
        priority=priority,
        related_type="incident",
        related_id=incident.id,
    )


@router.get("", response_model=Paginated[IncidentOut])
def list_incidents(
    pagination: Pagination = Depends(),
    status: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    vehicle_id: Optional[int] = Query(default=None),
    driver_id: Optional[int] = Query(default=None),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("incidents:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(Incident), Incident, user, organisation_id)
    if status:
        query = query.filter(Incident.status == status)
    if severity:
        query = query.filter(Incident.severity == severity)
    if vehicle_id:
        query = query.filter(Incident.vehicle_id == vehicle_id)
    if driver_id:
        query = query.filter(Incident.driver_id == driver_id)
    total = query.count()
    incidents = query.order_by(Incident.occurred_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[IncidentOut].create(
        [incident_out(incident) for incident in incidents], total, pagination.page, pagination.page_size
    )


@router.get("/summary", response_model=IncidentSummary)
def incident_summary(
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("incidents:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(Incident), Incident, user, organisation_id)
    incidents = query.all()
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    resolved_durations = []
    for incident in incidents:
        by_type[incident.incident_type] = by_type.get(incident.incident_type, 0) + 1
        by_severity[incident.severity] = by_severity.get(incident.severity, 0) + 1
        if incident.resolved_at and incident.occurred_at:
            resolved_durations.append((incident.resolved_at - incident.occurred_at).total_seconds() / 3600)
    return IncidentSummary(
        total=len(incidents),
        open=sum(1 for i in incidents if i.status == "new"),
        under_investigation=sum(1 for i in incidents if i.status == "under_investigation"),
        resolved=sum(1 for i in incidents if i.status == "resolved"),
        false_alerts=sum(1 for i in incidents if i.status == "false_alert"),
        critical=sum(1 for i in incidents if i.severity == "critical" and i.status != "resolved"),
        by_type=[{"type": key, "count": value} for key, value in sorted(by_type.items(), key=lambda kv: -kv[1])],
        by_severity=[{"severity": key, "count": value} for key, value in by_severity.items()],
        response_time_hours_avg=round(sum(resolved_durations) / len(resolved_durations), 1)
        if resolved_durations
        else None,
    )


@router.post("", response_model=IncidentOut, status_code=201)
def create_incident(
    payload: IncidentCreate,
    request: Request,
    user: User = Depends(require_permission("incidents:create")),
    db: Session = Depends(get_db),
):
    vehicle = db.get(Vehicle, payload.vehicle_id) if payload.vehicle_id else None
    driver = db.get(Driver, payload.driver_id) if payload.driver_id else None
    if payload.vehicle_id and not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if payload.driver_id and not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    if user.role != "super_admin":
        for obj in (vehicle, driver):
            if obj and obj.organisation_id != user.organisation_id:
                raise HTTPException(status_code=404, detail="Resource not found")

    organisation_id = (
        user.organisation_id
        or (vehicle.organisation_id if vehicle else None)
        or (driver.organisation_id if driver else None)
    )
    emergency_contact = {}
    if driver:
        emergency_contact = {
            "name": driver.emergency_contact_name,
            "phone": driver.emergency_contact_phone,
            "note": "Configured contact. Emergency services are not contacted automatically.",
        }

    incident = Incident(
        organisation_id=organisation_id,
        vehicle_id=vehicle.id if vehicle else None,
        driver_id=driver.id if driver else None,
        reporter_id=user.id,
        incident_type=payload.incident_type,
        title=payload.title.strip(),
        description=payload.description,
        severity=payload.severity,
        status="new",
        latitude=payload.latitude,
        longitude=payload.longitude,
        occurred_at=payload.occurred_at or datetime.utcnow(),
        evidence=payload.evidence or [],
        emergency_contact_json=emergency_contact,
    )
    db.add(incident)
    db.flush()

    if incident.severity in {"critical", "severe"}:
        create_notification(
            db,
            organisation_id=incident.organisation_id,
            notification_type="possible_accident",
            title="Serious incident reported - verification required",
            message=(
                f"{incident.title}. Verify driver safety and record the outcome before any external escalation. "
                "Emergency services are not contacted automatically."
            ),
            priority="urgent",
            related_type="incident",
            related_id=incident.id,
        )
    log_action(
        db,
        user=user,
        action="incident.create",
        resource_type="incident",
        resource_id=incident.id,
        detail={"severity": incident.severity, "type": incident.incident_type},
        request=request,
    )
    return incident_out(incident, vehicle)


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(
    incident_id: int,
    user: User = Depends(require_permission("incidents:read")),
    db: Session = Depends(get_db),
):
    return incident_out(load_incident(db, user, incident_id))


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    request: Request,
    user: User = Depends(require_permission("incidents:manage")),
    db: Session = Depends(get_db),
):
    incident = load_incident(db, user, incident_id)
    data = payload.model_dump(exclude_unset=True)

    if data.get("status"):
        _transition(incident, data["status"])
        if incident.status == "verified" and not incident.verified_at:
            incident.verified_at = datetime.utcnow()
            incident.verified_by_id = user.id
        if incident.status == "resolved" and not incident.resolved_at:
            incident.resolved_at = datetime.utcnow()
            incident.resolved_by_id = user.id
    if data.get("severity"):
        incident.severity = data["severity"]
    if data.get("title"):
        incident.title = data["title"]
    if data.get("description") is not None:
        incident.description = data["description"]
    if data.get("investigation_notes") is not None:
        incident.investigation_notes = data["investigation_notes"]
    if data.get("resolution_notes") is not None:
        incident.resolution_notes = data["resolution_notes"]
    if data.get("latitude") is not None:
        incident.latitude = data["latitude"]
    if data.get("longitude") is not None:
        incident.longitude = data["longitude"]
    db.flush()
    log_action(
        db,
        user=user,
        action="incident.update",
        resource_type="incident",
        resource_id=incident.id,
        detail={"status": incident.status, "fields": sorted(data.keys())},
        request=request,
    )
    _notify_incident(db, incident, f"updated - {incident.status.replace('_', ' ')}")
    return incident_out(incident)


@router.post("/{incident_id}/investigate", response_model=IncidentOut)
def start_investigation(
    incident_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_permission("incidents:manage")),
    db: Session = Depends(get_db),
):
    incident = load_incident(db, user, incident_id)
    _transition(incident, "under_investigation")
    if payload.get("notes"):
        incident.investigation_notes = payload["notes"]
    db.flush()
    log_action(db, user=user, action="incident.investigate", resource_type="incident", resource_id=incident.id, request=request)
    _notify_incident(db, incident, "moved to Under Investigation")
    return incident_out(incident)


@router.post("/{incident_id}/verify", response_model=IncidentOut)
def verify_incident(
    incident_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_permission("incidents:manage")),
    db: Session = Depends(get_db),
):
    incident = load_incident(db, user, incident_id)
    _transition(incident, "verified")
    incident.verified_at = datetime.utcnow()
    incident.verified_by_id = user.id
    if payload.get("notes"):
        incident.investigation_notes = payload["notes"]
    db.flush()
    log_action(db, user=user, action="incident.verify", resource_type="incident", resource_id=incident.id, request=request)
    _notify_incident(db, incident, "verified")
    return incident_out(incident)


@router.post("/{incident_id}/resolve", response_model=IncidentOut)
def resolve_incident(
    incident_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_permission("incidents:manage")),
    db: Session = Depends(get_db),
):
    incident = load_incident(db, user, incident_id)
    _transition(incident, "resolved")
    incident.resolved_at = datetime.utcnow()
    incident.resolved_by_id = user.id
    if payload.get("notes"):
        incident.resolution_notes = payload["notes"]
    db.flush()
    log_action(db, user=user, action="incident.resolve", resource_type="incident", resource_id=incident.id, request=request)
    _notify_incident(db, incident, "resolved", "medium")
    return incident_out(incident)


@router.post("/{incident_id}/false-alert", response_model=IncidentOut)
def mark_false_alert(
    incident_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_permission("incidents:manage")),
    db: Session = Depends(get_db),
):
    incident = load_incident(db, user, incident_id)
    _transition(incident, "false_alert")
    incident.resolution_notes = payload.get("notes", "Marked as false alert after review.")
    incident.resolved_at = datetime.utcnow()
    db.flush()
    log_action(db, user=user, action="incident.false_alert", resource_type="incident", resource_id=incident.id, request=request)
    return incident_out(incident)


@router.post("/{incident_id}/notes", response_model=IncidentOut)
def add_note(
    incident_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_permission("incidents:manage")),
    db: Session = Depends(get_db),
):
    incident = load_incident(db, user, incident_id)
    note = (payload.get("note") or "").strip()
    if not note:
        raise HTTPException(status_code=422, detail="note is required")
    stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    existing = incident.investigation_notes or ""
    incident.investigation_notes = f"{existing}\n[{stamp} - {user.full_name}] {note}".strip()
    db.flush()
    log_action(db, user=user, action="incident.note", resource_type="incident", resource_id=incident.id, request=request)
    return incident_out(incident)
