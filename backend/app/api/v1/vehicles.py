"""Vehicle management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import (
    Pagination,
    ensure_org_access,
    get_current_user,
    get_db,
    get_organisation,
    org_filter,
    require_permission,
)
from app.core.rbac import UserRole
from app.models import (
    Driver,
    DrivingEvent,
    GPSDevice,
    MaintenanceAlert,
    MaintenanceRecord,
    Trip,
    User,
    Vehicle,
    VehicleHealthReading,
    VehicleLocation,
)
from app.schemas.common import MessageResponse, Paginated
from app.schemas.fleet import (
    DriverOut,
    GeofenceOut,
    MaintenanceAlertOut,
    MaintenanceRecordOut,
    TripOut,
    VehicleCreate,
    VehicleHealthOut,
    VehicleOut,
    VehicleUpdate,
)
from app.schemas.safety import DrivingEventOut
from app.services import billing
from app.services.audit import log_action
from app.services.serializers import driver_out, vehicle_out

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


def load_vehicle(db: Session, user: User, vehicle_id: int) -> Vehicle:
    vehicle = (
        db.query(Vehicle)
        .options(joinedload(Vehicle.assigned_driver), joinedload(Vehicle.gps_device))
        .filter(Vehicle.id == vehicle_id)
        .first()
    )
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    ensure_org_access(vehicle.organisation_id, user)
    return vehicle


def _resolve_driver(db: Session, user: User, driver_id: Optional[int], organisation_id: Optional[int]) -> Optional[Driver]:
    if driver_id is None:
        return None
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Assigned driver not found")
    if user.role != UserRole.SUPER_ADMIN.value and driver.organisation_id != organisation_id:
        raise HTTPException(status_code=403, detail="Driver belongs to another organisation")
    return driver


def _resolve_device(db: Session, user: User, device_id: Optional[int], organisation_id: Optional[int]) -> Optional[GPSDevice]:
    if device_id is None:
        return None
    device = db.get(GPSDevice, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="GPS device not found")
    if user.role != UserRole.SUPER_ADMIN.value and device.organisation_id != organisation_id:
        raise HTTPException(status_code=403, detail="GPS device belongs to another organisation")
    return device


@router.get("", response_model=Paginated[VehicleOut])
def list_vehicles(
    pagination: Pagination = Depends(),
    status: Optional[str] = Query(default=None),
    vehicle_type: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    include_archived: bool = Query(default=False),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("vehicles:read")),
    db: Session = Depends(get_db),
):
    query = db.query(Vehicle).options(joinedload(Vehicle.assigned_driver), joinedload(Vehicle.gps_device))
    query = org_filter(query, Vehicle, user, organisation_id)
    if not include_archived:
        query = query.filter(Vehicle.is_archived.is_(False))
    if status:
        query = query.filter(Vehicle.status == status)
    if vehicle_type:
        query = query.filter(Vehicle.vehicle_type == vehicle_type)
    if search:
        needle = f"%{search}%"
        query = query.filter(
            Vehicle.registration_number.ilike(needle)
            | Vehicle.manufacturer.ilike(needle)
            | Vehicle.model.ilike(needle)
        )
    total = query.count()
    vehicles = query.order_by(Vehicle.created_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[VehicleOut].create(
        [vehicle_out(vehicle) for vehicle in vehicles], total, pagination.page, pagination.page_size
    )


@router.get("/meta/status-counts")
def vehicle_status_counts(
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("vehicles:read")),
    db: Session = Depends(get_db),
):
    query = db.query(Vehicle.status, func.count(Vehicle.id)).filter(Vehicle.is_archived.is_(False))
    query = org_filter(query, Vehicle, user, organisation_id)
    counts = {status: count for status, count in query.group_by(Vehicle.status).all()}
    return {"counts": counts, "total": sum(counts.values())}


@router.post("", response_model=VehicleOut, status_code=201)
def create_vehicle(
    payload: VehicleCreate,
    request: Request,
    organisation=Depends(get_organisation),
    user: User = Depends(require_permission("vehicles:create")),
    db: Session = Depends(get_db),
):
    if user.role != UserRole.SUPER_ADMIN.value:
        billing.assert_vehicle_quota(db, organisation)
    registration = payload.registration_number.upper()
    existing = (
        db.query(Vehicle)
        .filter(
            Vehicle.organisation_id == organisation.id,
            func.replace(Vehicle.registration_number, " ", "") == registration.replace(" ", ""),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="A vehicle with this registration number already exists")

    driver = _resolve_driver(db, user, payload.assigned_driver_id, organisation.id)
    device = _resolve_device(db, user, payload.gps_device_id, organisation.id)

    vehicle = Vehicle(
        organisation_id=organisation.id,
        registration_number=registration,
        vehicle_type=payload.vehicle_type.lower(),
        manufacturer=payload.manufacturer.strip(),
        model=payload.model.strip(),
        manufacturing_year=payload.manufacturing_year,
        fuel_type=payload.fuel_type,
        vin=payload.vin,
        assigned_driver_id=driver.id if driver else None,
        gps_device_id=device.id if device else None,
        status=payload.status,
        insurance_expiry=payload.insurance_expiry,
        mileage_km=payload.mileage_km,
        depot=payload.depot,
        notes=payload.notes,
        next_service_km=payload.mileage_km + 10000 if payload.mileage_km else None,
    )
    db.add(vehicle)
    db.flush()
    if device:
        device.vehicle_id = vehicle.id
    log_action(
        db,
        user=user,
        action="vehicle.create",
        resource_type="vehicle",
        resource_id=vehicle.id,
        detail={"registration": vehicle.registration_number, "type": vehicle.vehicle_type},
        request=request,
    )
    db.refresh(vehicle)
    return vehicle_out(vehicle)


@router.get("/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(vehicle_id: int, user: User = Depends(require_permission("vehicles:read")), db: Session = Depends(get_db)):
    return vehicle_out(load_vehicle(db, user, vehicle_id))


@router.patch("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdate,
    request: Request,
    user: User = Depends(require_permission("vehicles:update")),
    db: Session = Depends(get_db),
):
    vehicle = load_vehicle(db, user, vehicle_id)
    data = payload.model_dump(exclude_unset=True)

    if "registration_number" in data and data["registration_number"]:
        registration = data["registration_number"].upper()
        duplicate = (
            db.query(Vehicle)
            .filter(
                Vehicle.organisation_id == vehicle.organisation_id,
                func.replace(Vehicle.registration_number, " ", "") == registration.replace(" ", ""),
                Vehicle.id != vehicle.id,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Registration number is already in use")
        vehicle.registration_number = registration
    if "assigned_driver_id" in data:
        driver = _resolve_driver(db, user, data["assigned_driver_id"], vehicle.organisation_id)
        vehicle.assigned_driver_id = driver.id if driver else None
    if "gps_device_id" in data:
        device = _resolve_device(db, user, data["gps_device_id"], vehicle.organisation_id)
        vehicle.gps_device_id = device.id if device else None
        if device:
            device.vehicle_id = vehicle.id

    for field in (
        "vehicle_type", "manufacturer", "model", "fuel_type", "status",
        "insurance_expiry", "mileage_km", "depot", "notes", "vin", "manufacturing_year",
    ):
        if field in data and data[field] is not None:
            setattr(vehicle, field, data[field])
    db.flush()
    log_action(
        db,
        user=user,
        action="vehicle.update",
        resource_type="vehicle",
        resource_id=vehicle.id,
        detail={"fields": sorted(data.keys())},
        request=request,
    )
    db.refresh(vehicle)
    return vehicle_out(vehicle)


@router.delete("/{vehicle_id}", response_model=MessageResponse)
def archive_vehicle(
    vehicle_id: int,
    request: Request,
    user: User = Depends(require_permission("vehicles:delete")),
    db: Session = Depends(get_db),
):
    vehicle = load_vehicle(db, user, vehicle_id)
    vehicle.is_archived = True
    vehicle.archived_at = datetime.utcnow()
    vehicle.assigned_driver_id = None
    db.flush()
    log_action(
        db,
        user=user,
        action="vehicle.archive",
        resource_type="vehicle",
        resource_id=vehicle.id,
        detail={"registration": vehicle.registration_number},
        request=request,
    )
    return MessageResponse(message="Vehicle archived. Historical records are retained.")


@router.post("/{vehicle_id}/assign-driver", response_model=VehicleOut)
def assign_driver(
    vehicle_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_permission("vehicles:update")),
    db: Session = Depends(get_db),
):
    vehicle = load_vehicle(db, user, vehicle_id)
    driver_id = payload.get("driver_id")
    driver = _resolve_driver(db, user, driver_id, vehicle.organisation_id) if driver_id else None
    vehicle.assigned_driver_id = driver.id if driver else None
    db.flush()
    log_action(
        db,
        user=user,
        action="vehicle.assign_driver",
        resource_type="vehicle",
        resource_id=vehicle.id,
        detail={"driver_id": driver.id if driver else None},
        request=request,
    )
    return vehicle_out(vehicle)


@router.get("/{vehicle_id}/overview")
def vehicle_overview(vehicle_id: int, user: User = Depends(require_permission("vehicles:read")), db: Session = Depends(get_db)):
    vehicle = load_vehicle(db, user, vehicle_id)
    health = (
        db.query(VehicleHealthReading)
        .filter(VehicleHealthReading.vehicle_id == vehicle.id)
        .order_by(VehicleHealthReading.recorded_at.desc())
        .first()
    )
    last_location = (
        db.query(VehicleLocation)
        .filter(VehicleLocation.vehicle_id == vehicle.id)
        .order_by(VehicleLocation.recorded_at.desc())
        .first()
    )
    open_alerts = (
        db.query(MaintenanceAlert)
        .filter(MaintenanceAlert.vehicle_id == vehicle.id, MaintenanceAlert.status == "open")
        .all()
    )
    recent_events = (
        db.query(DrivingEvent)
        .filter(DrivingEvent.vehicle_id == vehicle.id)
        .order_by(DrivingEvent.occurred_at.desc())
        .limit(6)
        .all()
    )
    trips_count = db.query(func.count(Trip.id)).filter(Trip.vehicle_id == vehicle.id).scalar() or 0
    return {
        "vehicle": vehicle_out(vehicle).model_dump(),
        "health": VehicleHealthOut(
            vehicle_id=vehicle.id,
            registration_number=vehicle.registration_number,
            status=vehicle.status,
            health_score=health.health_score if health else 100.0,
            engine_temperature_c=health.engine_temperature_c if health else None,
            battery_voltage=health.battery_voltage if health else None,
            fuel_level_pct=health.fuel_level_pct if health else None,
            fuel_consumption_l_per_100km=health.fuel_consumption_l_per_100km if health else None,
            fault_codes=health.fault_codes if health else [],
            mileage_km=vehicle.mileage_km,
            is_simulated=bool(health.is_simulated) if health else True,
            recorded_at=health.recorded_at if health else None,
            next_service_km=vehicle.next_service_km,
        ).model_dump(),
        "last_location": {
            "latitude": last_location.latitude,
            "longitude": last_location.longitude,
            "speed_kph": last_location.speed_kph,
            "recorded_at": last_location.recorded_at.isoformat() + "Z",
            "is_simulated": last_location.is_simulated,
        }
        if last_location
        else None,
        "open_alerts": [MaintenanceAlertOut.model_validate(alert).model_dump() for alert in open_alerts],
        "recent_events": [DrivingEventOut.model_validate(event).model_dump() for event in recent_events],
        "trips_count": trips_count,
    }


@router.get("/{vehicle_id}/locations", response_model=list[dict])
def vehicle_locations(
    vehicle_id: int,
    limit: int = Query(default=500, ge=1, le=5000),
    from_time: Optional[datetime] = Query(default=None, alias="from"),
    to_time: Optional[datetime] = Query(default=None, alias="to"),
    user: User = Depends(require_permission("tracking:read")),
    db: Session = Depends(get_db),
):
    vehicle = load_vehicle(db, user, vehicle_id)
    query = db.query(VehicleLocation).filter(VehicleLocation.vehicle_id == vehicle.id)
    if from_time:
        query = query.filter(VehicleLocation.recorded_at >= from_time)
    if to_time:
        query = query.filter(VehicleLocation.recorded_at <= to_time)
    rows = query.order_by(VehicleLocation.recorded_at.asc()).limit(limit).all()
    return [
        {
            "latitude": row.latitude,
            "longitude": row.longitude,
            "speed_kph": row.speed_kph,
            "heading": row.heading,
            "recorded_at": row.recorded_at.isoformat() + "Z",
            "is_simulated": row.is_simulated,
            "source": row.source,
        }
        for row in rows
    ]


@router.get("/{vehicle_id}/trips", response_model=Paginated[TripOut])
def vehicle_trips(
    vehicle_id: int,
    pagination: Pagination = Depends(),
    user: User = Depends(require_permission("tracking:read")),
    db: Session = Depends(get_db),
):
    vehicle = load_vehicle(db, user, vehicle_id)
    query = db.query(Trip).filter(Trip.vehicle_id == vehicle.id)
    total = query.count()
    trips = query.order_by(Trip.start_time.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    items = []
    for trip in trips:
        driver = db.get(Driver, trip.driver_id) if trip.driver_id else None
        item = TripOut.model_validate(trip)
        item.driver_name = driver.full_name if driver else None
        items.append(item)
    return Paginated[TripOut].create(items, total, pagination.page, pagination.page_size)


@router.get("/{vehicle_id}/events", response_model=Paginated[DrivingEventOut])
def vehicle_events(
    vehicle_id: int,
    pagination: Pagination = Depends(),
    user: User = Depends(require_permission("behaviour:read")),
    db: Session = Depends(get_db),
):
    vehicle = load_vehicle(db, user, vehicle_id)
    query = db.query(DrivingEvent).filter(DrivingEvent.vehicle_id == vehicle.id)
    total = query.count()
    events = query.order_by(DrivingEvent.occurred_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[DrivingEventOut].create(
        [_event_out(event, db) for event in events], total, pagination.page, pagination.page_size
    )


def _event_out(event: DrivingEvent, db: Session) -> DrivingEventOut:
    vehicle = db.get(Vehicle, event.vehicle_id)
    driver = db.get(Driver, event.driver_id) if event.driver_id else None
    item = DrivingEventOut.model_validate(event)
    item.registration_number = vehicle.registration_number if vehicle else None
    item.driver_name = driver.full_name if driver else None
    return item


@router.get("/{vehicle_id}/health", response_model=list[VehicleHealthOut])
def vehicle_health_history(
    vehicle_id: int,
    limit: int = Query(default=20, ge=1, le=200),
    user: User = Depends(require_permission("maintenance:read")),
    db: Session = Depends(get_db),
):
    vehicle = load_vehicle(db, user, vehicle_id)
    readings = (
        db.query(VehicleHealthReading)
        .filter(VehicleHealthReading.vehicle_id == vehicle.id)
        .order_by(VehicleHealthReading.recorded_at.desc())
        .limit(limit)
        .all()
    )
    return [
        VehicleHealthOut(
            vehicle_id=vehicle.id,
            registration_number=vehicle.registration_number,
            status=vehicle.status,
            health_score=reading.health_score,
            engine_temperature_c=reading.engine_temperature_c,
            battery_voltage=reading.battery_voltage,
            fuel_level_pct=reading.fuel_level_pct,
            fuel_consumption_l_per_100km=reading.fuel_consumption_l_per_100km,
            fault_codes=reading.fault_codes or [],
            mileage_km=reading.odometer_km,
            is_simulated=reading.is_simulated,
            recorded_at=reading.recorded_at,
        )
        for reading in readings
    ]


@router.get("/{vehicle_id}/maintenance", response_model=list[MaintenanceRecordOut])
def vehicle_maintenance(
    vehicle_id: int,
    user: User = Depends(require_permission("maintenance:read")),
    db: Session = Depends(get_db),
):
    vehicle = load_vehicle(db, user, vehicle_id)
    records = (
        db.query(MaintenanceRecord)
        .filter(MaintenanceRecord.vehicle_id == vehicle.id)
        .order_by(MaintenanceRecord.performed_at.desc())
        .limit(50)
        .all()
    )
    return [MaintenanceRecordOut.model_validate(record) for record in records]
