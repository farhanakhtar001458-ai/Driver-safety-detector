"""Vehicle health and predictive maintenance."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import Pagination, get_db, get_organisation, org_filter, require_permission
from app.models import MaintenanceAlert, MaintenanceRecord, Organisation, User, Vehicle, VehicleHealthReading
from app.schemas.common import MessageResponse, Paginated
from app.schemas.fleet import (
    MaintenanceAlertOut,
    MaintenanceRecordIn,
    MaintenanceRecordOut,
    VehicleHealthOut,
)
from app.services.audit import log_action
from app.services.notifications import create_notification

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


def _alert_out(alert: MaintenanceAlert) -> MaintenanceAlertOut:
    item = MaintenanceAlertOut.model_validate(alert)
    item.registration_number = alert.vehicle.registration_number if alert.vehicle else None
    return item


def _health_row(db: Session, vehicle: Vehicle, reading: Optional[VehicleHealthReading]) -> VehicleHealthOut:
    days_to_service = None
    if vehicle.next_service_km and reading:
        remaining = vehicle.next_service_km - vehicle.mileage_km
        days_to_service = max(0, int(remaining / 80)) if remaining > 0 else 0
    return VehicleHealthOut(
        vehicle_id=vehicle.id,
        registration_number=vehicle.registration_number,
        status=vehicle.status,
        health_score=reading.health_score if reading else 100.0,
        engine_temperature_c=reading.engine_temperature_c if reading else None,
        battery_voltage=reading.battery_voltage if reading else None,
        fuel_level_pct=reading.fuel_level_pct if reading else None,
        fuel_consumption_l_per_100km=reading.fuel_consumption_l_per_100km if reading else None,
        fault_codes=reading.fault_codes if reading else [],
        mileage_km=vehicle.mileage_km,
        is_simulated=bool(reading.is_simulated) if reading else True,
        recorded_at=reading.recorded_at if reading else None,
        next_service_km=vehicle.next_service_km,
        days_to_service=days_to_service,
    )


@router.get("/health", response_model=list[VehicleHealthOut])
def fleet_health(
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("maintenance:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(Vehicle), Vehicle, user, organisation_id).filter(Vehicle.is_archived.is_(False))
    vehicles = query.order_by(Vehicle.id).all()
    readings: dict[int, VehicleHealthReading] = {}
    rows = (
        db.query(VehicleHealthReading)
        .filter(VehicleHealthReading.vehicle_id.in_([v.id for v in vehicles]))
        .order_by(VehicleHealthReading.recorded_at.desc())
        .all()
        if vehicles
        else []
    )
    for reading in rows:
        readings.setdefault(reading.vehicle_id, reading)
    return [_health_row(db, vehicle, readings.get(vehicle.id)) for vehicle in vehicles]


@router.get("/alerts", response_model=Paginated[MaintenanceAlertOut])
def list_alerts(
    pagination: Pagination = Depends(),
    status: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("maintenance:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(MaintenanceAlert), MaintenanceAlert, user, organisation_id)
    if status:
        query = query.filter(MaintenanceAlert.status == status)
    if severity:
        query = query.filter(MaintenanceAlert.severity == severity)
    total = query.count()
    alerts = query.order_by(MaintenanceAlert.created_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[MaintenanceAlertOut].create(
        [_alert_out(alert) for alert in alerts], total, pagination.page, pagination.page_size
    )


@router.post("/alerts/{alert_id}/resolve", response_model=MaintenanceAlertOut)
def resolve_alert(
    alert_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_permission("maintenance:manage")),
    db: Session = Depends(get_db),
):
    alert = db.get(MaintenanceAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Maintenance alert not found")
    from app.core.deps import ensure_org_access

    ensure_org_access(alert.organisation_id, user)
    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by_id = user.id
    db.flush()
    log_action(
        db,
        user=user,
        action="maintenance.alert.resolve",
        resource_type="maintenance_alert",
        resource_id=alert.id,
        detail={"notes": payload.get("notes")},
        request=request,
    )
    return _alert_out(alert)


@router.get("/records", response_model=Paginated[MaintenanceRecordOut])
def list_records(
    pagination: Pagination = Depends(),
    vehicle_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("maintenance:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(MaintenanceRecord), MaintenanceRecord, user, organisation_id)
    if vehicle_id:
        query = query.filter(MaintenanceRecord.vehicle_id == vehicle_id)
    if status:
        query = query.filter(MaintenanceRecord.status == status)
    total = query.count()
    records = query.order_by(MaintenanceRecord.performed_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[MaintenanceRecordOut].create(
        [MaintenanceRecordOut.model_validate(record) for record in records],
        total,
        pagination.page,
        pagination.page_size,
    )


@router.post("/records", response_model=MaintenanceRecordOut, status_code=201)
def create_record(
    payload: MaintenanceRecordIn,
    request: Request,
    user: User = Depends(require_permission("maintenance:manage")),
    db: Session = Depends(get_db),
):
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    from app.core.deps import ensure_org_access

    ensure_org_access(vehicle.organisation_id, user)
    record = MaintenanceRecord(
        organisation_id=vehicle.organisation_id,
        created_by_id=user.id,
        performed_at=payload.performed_at or datetime.utcnow(),
        **payload.model_dump(exclude={"performed_at"}),
    )
    db.add(record)
    if record.status == "completed":
        vehicle.last_service_at = (record.performed_at or datetime.utcnow()).date()
        vehicle.next_service_km = record.next_due_km or (vehicle.mileage_km + 10000)
    db.flush()
    log_action(
        db,
        user=user,
        action="maintenance.record.create",
        resource_type="maintenance_record",
        resource_id=record.id,
        detail={"vehicle_id": vehicle.id, "type": record.record_type},
        request=request,
    )
    return MaintenanceRecordOut.model_validate(record)


@router.patch("/records/{record_id}", response_model=MaintenanceRecordOut)
def update_record(
    record_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_permission("maintenance:manage")),
    db: Session = Depends(get_db),
):
    record = db.get(MaintenanceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    from app.core.deps import ensure_org_access

    ensure_org_access(record.organisation_id, user)
    for key in ("title", "description", "status", "cost", "next_due_km", "next_due_date", "vendor"):
        if key in payload and payload[key] is not None:
            setattr(record, key, payload[key])
    db.flush()
    log_action(db, user=user, action="maintenance.record.update", resource_type="maintenance_record", resource_id=record.id, request=request)
    return MaintenanceRecordOut.model_validate(record)


@router.get("/schedule", response_model=list[dict])
def maintenance_schedule(
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("maintenance:read")),
    db: Session = Depends(get_db),
):
    vehicles = org_filter(db.query(Vehicle), Vehicle, user, organisation_id).filter(Vehicle.is_archived.is_(False)).all()
    alerts = org_filter(db.query(MaintenanceAlert), MaintenanceAlert, user, organisation_id).filter(
        MaintenanceAlert.status == "open"
    ).all()
    by_vehicle: dict[int, list[MaintenanceAlert]] = {}
    for alert in alerts:
        by_vehicle.setdefault(alert.vehicle_id, []).append(alert)
    schedule = []
    now = datetime.utcnow()
    for vehicle in vehicles:
        vehicle_alerts = by_vehicle.get(vehicle.id, [])
        next_service_km = vehicle.next_service_km
        due_in_km = (next_service_km - vehicle.mileage_km) if next_service_km else None
        if due_in_km is not None and due_in_km <= 0:
            urgency = "overdue"
        elif vehicle_alerts:
            urgency = "attention"
        elif due_in_km is not None and due_in_km < 2000:
            urgency = "soon"
        else:
            urgency = "ok"
        schedule.append(
            {
                "vehicle_id": vehicle.id,
                "registration_number": vehicle.registration_number,
                "status": vehicle.status,
                "mileage_km": round(vehicle.mileage_km, 1),
                "next_service_km": next_service_km,
                "due_in_km": round(due_in_km, 1) if due_in_km is not None else None,
                "last_service_at": vehicle.last_service_at.isoformat() if vehicle.last_service_at else None,
                "open_alerts": len(vehicle_alerts),
                "urgency": urgency,
            }
        )
    schedule.sort(key=lambda item: {"overdue": 0, "attention": 1, "soon": 2, "ok": 3}[item["urgency"]])
    return schedule


@router.post("/predict/{vehicle_id}", response_model=dict)
def predict_maintenance(
    vehicle_id: int,
    request: Request,
    user: User = Depends(require_permission("maintenance:read")),
    db: Session = Depends(get_db),
):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    from app.core.deps import ensure_org_access

    ensure_org_access(vehicle.organisation_id, user)

    reading = (
        db.query(VehicleHealthReading)
        .filter(VehicleHealthReading.vehicle_id == vehicle.id)
        .order_by(VehicleHealthReading.recorded_at.desc())
        .first()
    )
    open_alerts = (
        db.query(MaintenanceAlert)
        .filter(MaintenanceAlert.vehicle_id == vehicle.id, MaintenanceAlert.status == "open")
        .all()
    )
    recommendations = []
    confidence = 0.6
    if reading:
        confidence = 0.82 if not reading.is_simulated else 0.45
        if reading.engine_temperature_c and reading.engine_temperature_c > 105:
            recommendations.append(
                {
                    "type": "cooling_system",
                    "priority": "high",
                    "title": "Inspect cooling system",
                    "reason": f"Engine temperature {reading.engine_temperature_c} C is above the normal range.",
                }
            )
        if reading.battery_voltage and reading.battery_voltage < 12.2:
            recommendations.append(
                {
                    "type": "battery",
                    "priority": "high",
                    "title": "Test battery and charging system",
                    "reason": f"Battery voltage {reading.battery_voltage} V is below the healthy threshold.",
                }
            )
        for code in reading.fault_codes or []:
            recommendations.append(
                {
                    "type": "fault_code",
                    "priority": "high" if code.startswith("P0") else "medium",
                    "title": f"Diagnose fault code {code}",
                    "reason": "ECU reported a diagnostic trouble code that requires inspection.",
                }
            )
    due_in_km = (
        (vehicle.next_service_km - vehicle.mileage_km) if vehicle.next_service_km else None
    )
    if due_in_km is not None and due_in_km <= 0:
        recommendations.append(
            {
                "type": "service",
                "priority": "high",
                "title": "Schedule overdue service",
                "reason": f"Vehicle is {abs(due_in_km):.0f} km past its service interval.",
            }
        )
    elif due_in_km is not None and due_in_km < 2000:
        recommendations.append(
            {
                "type": "service",
                "priority": "medium",
                "title": "Book service in the next 2,000 km",
                "reason": f"Approximately {due_in_km:.0f} km remain before the next service interval.",
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "type": "routine",
                "priority": "low",
                "title": "Continue routine maintenance",
                "reason": "No diagnostic threshold was triggered in the latest reading.",
            }
        )
    # Component risk is a transparent rule-based estimate derived from the readings
    # actually available. No cost figure is produced because the platform has no
    # parts/labour price data; the UI says so instead of inventing a number.
    components: list[dict] = []

    def add_component(component: str, probability: float, driver: str) -> None:
        components.append({"component": component, "probability": round(probability, 2), "basis": driver})

    if reading:
        temperature = reading.engine_temperature_c or 0
        if temperature >= 105:
            add_component("cooling_system", 0.85, f"engine temperature {temperature} C")
        elif temperature >= 98:
            add_component("cooling_system", 0.45, f"engine temperature {temperature} C")

        voltage = reading.battery_voltage or 0
        if voltage and voltage < 12.2:
            add_component("battery", 0.7, f"battery voltage {voltage} V")
        elif voltage and voltage < 12.6:
            add_component("battery", 0.3, f"battery voltage {voltage} V")

        if (reading.fault_codes or []):
            add_component("engine_management", min(0.9, 0.35 + 0.2 * len(reading.fault_codes or [])),
                          "ECU fault codes present")

        if reading.fuel_consumption_l_per_100km and reading.fuel_consumption_l_per_100km > 0:
            add_component("fuel_system", 0.2, "elevated fuel consumption reading")
    else:
        add_component("general", 0.25, "no diagnostic reading available")

    if vehicle.mileage_km and vehicle.mileage_km > 150000:
        add_component("drivetrain", 0.35, f"odometer {vehicle.mileage_km:.0f} km")
    if due_in_km is not None and due_in_km <= 0:
        add_component("service_interval", 0.5, f"service overdue by {abs(due_in_km):.0f} km")

    components.sort(key=lambda item: item["probability"], reverse=True)
    failure_probability = round(min(0.95, max((item["probability"] for item in components), default=0.1)), 2)
    if failure_probability >= 0.7:
        risk_level = "high"
    elif failure_probability >= 0.4:
        risk_level = "medium"
    else:
        risk_level = "low"

    primary = recommendations[0] if recommendations else {
        "title": "No action required", "reason": "No diagnostic threshold was triggered."
    }
    data_sources: list[str] = []
    if reading:
        data_sources.append("latest diagnostic reading")
    if due_in_km is not None:
        data_sources.append("service schedule")
    if open_alerts:
        data_sources.append("open maintenance alerts")

    log_action(
        db,
        user=user,
        action="maintenance.predict",
        resource_type="vehicle",
        resource_id=vehicle.id,
        request=request,
    )
    return {
        "vehicle_id": vehicle.id,
        "registration_number": vehicle.registration_number,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "method": "rule_based",
        "failure_probability": failure_probability,
        "risk_level": risk_level,
        "components": components,
        "estimated_cost": None,
        "cost_note": "Not estimated: the platform has no parts or labour price data for this fleet.",
        "recommendation": f"{primary['title']}. {primary['reason']}",
        "recommendations": recommendations,
        "confidence": confidence,
        "is_estimated": True,
        "data_is_simulated": bool(reading.is_simulated) if reading else True,
        "is_simulated": bool(reading.is_simulated) if reading else True,
        "data_sources": data_sources,
        "open_alerts": len(open_alerts),
        "disclaimer": (
            "Maintenance predictions are rule-based estimates from available diagnostic data. They are not a "
            "substitute for a qualified vehicle inspection."
        ),
    }
