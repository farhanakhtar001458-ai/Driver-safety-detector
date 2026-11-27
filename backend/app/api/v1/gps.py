"""GPS ingestion, live tracking and geofencing."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import (
    Pagination,
    ensure_org_access,
    get_db,
    get_device,
    get_current_user,
    get_organisation,
    org_filter,
    require_permission,
)
from app.models import (
    Driver,
    DrivingEvent,
    Geofence,
    GPSDevice,
    Organisation,
    Trip,
    User,
    Vehicle,
    VehicleLocation,
)
from app.schemas.common import MessageResponse, Paginated
from app.schemas.fleet import (
    GeofenceIn,
    GeofenceOut,
    GPSIngestRequest,
    GPSIngestResponse,
    LiveVehicleOut,
    PhoneLocationRequest,
    LocationOut,
)
from app.services import telemetry
from app.services.ai.rules_engine import haversine_km
from app.services.audit import log_action
from app.services.notifications import create_notification
from app.services.serializers import vehicle_out

router = APIRouter(prefix="/gps", tags=["GPS & Tracking"])


def _phone_vehicles(db: Session, user: User):
    """Phones may only report for their tenant; drivers only for assigned vehicles."""
    if not user.organisation_id or user.role not in {"org_admin", "fleet_manager", "driver"}:
        raise HTTPException(status_code=403, detail="Phone GPS is not available for this role")
    query = db.query(Vehicle).filter(
        Vehicle.organisation_id == user.organisation_id, Vehicle.is_archived.is_(False)
    )
    if user.role == "driver":
        query = query.join(Driver, Vehicle.assigned_driver_id == Driver.id).filter(
            Driver.user_id == user.id, Driver.organisation_id == user.organisation_id
        )
    return query


@router.get("/phone/vehicles")
def phone_vehicles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    vehicles = _phone_vehicles(db, user).order_by(Vehicle.registration_number).all()
    return [{"id": vehicle.id, "registration_number": vehicle.registration_number} for vehicle in vehicles]


@router.post("/phone", status_code=201)
def phone_location(payload: PhoneLocationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Save a live phone position. Does not infer trips, ignition or safety events."""
    vehicle = _phone_vehicles(db, user).filter(Vehicle.id == payload.vehicle_id).first()
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found or not assigned to you")
    # Current schema requires numeric speed/heading and ignition. Defaults are
    # placeholders, not measurements. The UI labels phone telemetry accordingly.
    location = VehicleLocation(
        organisation_id=vehicle.organisation_id, vehicle_id=vehicle.id, device_id=None,
        latitude=payload.latitude, longitude=payload.longitude,
        speed_kph=payload.speed_kph if payload.speed_kph is not None else 0,
        heading=payload.heading if payload.heading is not None else 0,
        accuracy_m=payload.accuracy_m, odometer_km=vehicle.mileage_km or 0,
        ignition_on=False, source="phone", is_simulated=False, recorded_at=datetime.utcnow(),
    )
    db.add(location)
    db.flush()
    return {"accepted": 1, "vehicle_id": vehicle.id, "source": "phone"}


@router.post("/ingest", response_model=GPSIngestResponse)
def ingest_gps(
    payload: GPSIngestRequest,
    request: Request,
    device: GPSDevice = Depends(get_device),
    db: Session = Depends(get_db),
):
    """Authenticated telemetry ingestion for physical GPS devices.

    The device is authenticated with ``X-Device-Key``. A device is bound to one
    vehicle; ``vehicle_id`` in the body must match that binding.
    """
    vehicle_id = payload.vehicle_id or device.vehicle_id
    if not vehicle_id:
        raise HTTPException(status_code=400, detail="Device is not bound to a vehicle; pass vehicle_id")
    if device.vehicle_id and payload.vehicle_id and payload.vehicle_id != device.vehicle_id:
        raise HTTPException(status_code=403, detail="Device is bound to a different vehicle")
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if device.organisation_id != vehicle.organisation_id:
        raise HTTPException(status_code=403, detail="Device and vehicle belong to different organisations")

    points = []
    for point in payload.points:
        points.append(
            {
                "latitude": point.latitude,
                "longitude": point.longitude,
                "speed_kph": point.speed_kph,
                "heading": point.heading,
                "accuracy_m": point.accuracy_m,
                "altitude_m": point.altitude_m,
                "odometer_km": point.odometer_km,
                "ignition_on": point.ignition_on,
                "recorded_at": point.recorded_at or datetime.utcnow(),
            }
        )
        if point.fuel_level_pct is not None or point.engine_temperature_c is not None:
            telemetry.record_health(
                db,
                vehicle,
                engine_temperature_c=point.engine_temperature_c,
                battery_voltage=point.battery_voltage,
                fuel_level_pct=point.fuel_level_pct,
                fault_codes=point.fault_codes,
                source="device",
                is_simulated=False,
                recorded_at=point.recorded_at,
            )

    accepted, events = telemetry.ingest_batch(
        db, vehicle, points, source="device", is_simulated=False, device=device
    )

    # Geofence evaluation on the final point (once per batch).
    if points:
        _evaluate_geofences(db, vehicle, points[-1])

    high_severity = [event for event in events if event.severity in {"high", "critical"}]
    if high_severity:
        create_notification(
            db,
            organisation_id=vehicle.organisation_id,
            notification_type="speeding_alert" if any(e.event_type == "speeding" for e in high_severity) else "harsh_braking_alert",
            title=f"Safety event on {vehicle.registration_number}",
            message=(
                f"{len(high_severity)} high-severity event(s) recorded: "
                + ", ".join(sorted({e.event_type for e in high_severity}))
                + "."
            ),
            priority="high" if any(e.severity == "high" for e in high_severity) else "urgent",
            related_type="vehicle",
            related_id=vehicle.id,
        )
    db.flush()
    return GPSIngestResponse(
        accepted=accepted,
        events_created=len(events),
        vehicle_id=vehicle.id,
        simulated=False,
    )


def _evaluate_geofences(db: Session, vehicle: Vehicle, point: dict) -> None:
    fences = (
        db.query(Geofence)
        .filter(Geofence.organisation_id == vehicle.organisation_id, Geofence.is_active.is_(True))
        .all()
    )
    if not fences:
        return
    outside = [
        fence
        for fence in fences
        if haversine_km(fence.center_latitude, fence.center_longitude, point["latitude"], point["longitude"])
        > fence.radius_meters / 1000.0
    ]
    if len(outside) == len(fences):
        # Throttle: one breach event per vehicle per hour.
        recent = (
            db.query(DrivingEvent)
            .filter(
                DrivingEvent.vehicle_id == vehicle.id,
                DrivingEvent.event_type == "geofence_breach",
                DrivingEvent.occurred_at >= datetime.utcnow() - timedelta(hours=1),
            )
            .first()
        )
        if not recent:
            db.add(
                DrivingEvent(
                    organisation_id=vehicle.organisation_id,
                    vehicle_id=vehicle.id,
                    driver_id=vehicle.assigned_driver_id,
                    event_type="geofence_breach",
                    severity="medium",
                    latitude=point["latitude"],
                    longitude=point["longitude"],
                    speed_kph=point["speed_kph"],
                    sensor_data={"outside_geofences": [f.name for f in outside]},
                    recommended_action="Confirm the route plan and whether the deviation was authorised.",
                    is_simulated=False,
                    source="device",
                    occurred_at=point["recorded_at"],
                )
            )
            create_notification(
                db,
                organisation_id=vehicle.organisation_id,
                notification_type="route_deviation",
                title=f"Geofence breach - {vehicle.registration_number}",
                message="Vehicle is outside all active geofences. Confirm the route with the driver.",
                priority="high",
                related_type="vehicle",
                related_id=vehicle.id,
            )


def _latest_location(db: Session, vehicle_id: int) -> Optional[VehicleLocation]:
    return (
        db.query(VehicleLocation)
        .filter(VehicleLocation.vehicle_id == vehicle_id)
        .order_by(VehicleLocation.recorded_at.desc())
        .first()
    )


def _live_row(db: Session, vehicle: Vehicle, location: Optional[VehicleLocation]) -> Optional[LiveVehicleOut]:
    if not location:
        return None
    today = datetime.utcnow().date()
    distance = float(
        db.query(func.coalesce(func.sum(Trip.distance_km), 0.0))
        .filter(Trip.vehicle_id == vehicle.id, Trip.start_time >= datetime.combine(today, datetime.min.time()))
        .scalar()
        or 0.0
    )
    return LiveVehicleOut(
        vehicle_id=vehicle.id,
        registration_number=vehicle.registration_number,
        vehicle_type=vehicle.vehicle_type,
        status=vehicle.status,
        driver_name=vehicle.assigned_driver.full_name if vehicle.assigned_driver else None,
        latitude=location.latitude,
        longitude=location.longitude,
        speed_kph=location.speed_kph,
        heading=location.heading,
        ignition_on=location.ignition_on,
        last_seen=location.recorded_at,
        is_simulated=location.is_simulated,
        today_distance_km=round(distance, 1),
        source=location.source,
    )


@router.get("/live", response_model=list[LiveVehicleOut])
def live_fleet(
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("tracking:read")),
    db: Session = Depends(get_db),
):
    query = db.query(Vehicle).options(joinedload(Vehicle.assigned_driver))
    query = org_filter(query, Vehicle, user, organisation_id).filter(Vehicle.is_archived.is_(False))
    vehicles = query.order_by(Vehicle.id).all()
    rows = []
    for vehicle in vehicles:
        row = _live_row(db, vehicle, _latest_location(db, vehicle.id))
        if row:
            rows.append(row)
    return rows


@router.get("/vehicles/{vehicle_id}/latest", response_model=LocationOut)
def latest_location(
    vehicle_id: int,
    user: User = Depends(require_permission("tracking:read")),
    db: Session = Depends(get_db),
):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    ensure_org_access(vehicle.organisation_id, user)
    location = _latest_location(db, vehicle.id)
    if not location:
        raise HTTPException(status_code=404, detail="No telemetry recorded for this vehicle")
    return LocationOut.model_validate(location)


@router.get("/vehicles/{vehicle_id}/history", response_model=Paginated[LocationOut])
def location_history(
    vehicle_id: int,
    pagination: Pagination = Depends(),
    from_time: Optional[datetime] = Query(default=None, alias="from"),
    to_time: Optional[datetime] = Query(default=None, alias="to"),
    user: User = Depends(require_permission("tracking:read")),
    db: Session = Depends(get_db),
):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    ensure_org_access(vehicle.organisation_id, user)
    query = db.query(VehicleLocation).filter(VehicleLocation.vehicle_id == vehicle.id)
    if from_time:
        query = query.filter(VehicleLocation.recorded_at >= from_time)
    if to_time:
        query = query.filter(VehicleLocation.recorded_at <= to_time)
    total = query.count()
    rows = query.order_by(VehicleLocation.recorded_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[LocationOut].create(
        [LocationOut.model_validate(row) for row in rows], total, pagination.page, pagination.page_size
    )


# --------------------------------------------------------------------------
# Geofences
# --------------------------------------------------------------------------
@router.get("/geofences", response_model=list[GeofenceOut])
def list_geofences(
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("tracking:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(Geofence), Geofence, user, organisation_id)
    return [GeofenceOut.model_validate(fence) for fence in query.order_by(Geofence.created_at.desc()).all()]


@router.post("/geofences", response_model=GeofenceOut, status_code=201)
def create_geofence(
    payload: GeofenceIn,
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    user: User = Depends(require_permission("tracking:manage")),
    db: Session = Depends(get_db),
):
    fence = Geofence(
        organisation_id=organisation.id,
        created_by_id=user.id,
        **payload.model_dump(),
    )
    db.add(fence)
    db.flush()
    log_action(
        db,
        user=user,
        action="geofence.create",
        resource_type="geofence",
        resource_id=fence.id,
        detail={"name": fence.name, "radius_m": fence.radius_meters},
        request=request,
    )
    return GeofenceOut.model_validate(fence)


@router.patch("/geofences/{geofence_id}", response_model=GeofenceOut)
def update_geofence(
    geofence_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_permission("tracking:manage")),
    db: Session = Depends(get_db),
):
    fence = db.get(Geofence, geofence_id)
    if not fence:
        raise HTTPException(status_code=404, detail="Geofence not found")
    ensure_org_access(fence.organisation_id, user)
    for key in ("name", "description", "center_latitude", "center_longitude", "radius_meters", "alert_on_enter", "alert_on_exit", "is_active"):
        if key in payload and payload[key] is not None:
            setattr(fence, key, payload[key])
    db.flush()
    log_action(db, user=user, action="geofence.update", resource_type="geofence", resource_id=fence.id, request=request)
    return GeofenceOut.model_validate(fence)


@router.delete("/geofences/{geofence_id}", response_model=MessageResponse)
def delete_geofence(
    geofence_id: int,
    request: Request,
    user: User = Depends(require_permission("tracking:manage")),
    db: Session = Depends(get_db),
):
    fence = db.get(Geofence, geofence_id)
    if not fence:
        raise HTTPException(status_code=404, detail="Geofence not found")
    ensure_org_access(fence.organisation_id, user)
    db.delete(fence)
    db.flush()
    log_action(db, user=user, action="geofence.delete", resource_type="geofence", resource_id=geofence_id, request=request)
    return MessageResponse(message="Geofence deleted")


@router.get("/trails", response_model=list[dict])
def recent_trails(
    minutes: int = Query(default=30, ge=5, le=360),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("tracking:read")),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(minutes=minutes)
    vehicle_query = org_filter(db.query(Vehicle), Vehicle, user, organisation_id).filter(Vehicle.is_archived.is_(False))
    vehicles = vehicle_query.all()
    ids = [vehicle.id for vehicle in vehicles]
    if not ids:
        return []
    rows = (
        db.query(VehicleLocation)
        .filter(VehicleLocation.vehicle_id.in_(ids), VehicleLocation.recorded_at >= since)
        .order_by(VehicleLocation.vehicle_id, VehicleLocation.recorded_at.asc())
        .all()
    )
    by_vehicle: dict[int, list[VehicleLocation]] = {}
    for row in rows:
        by_vehicle.setdefault(row.vehicle_id, []).append(row)
    result = []
    for vehicle in vehicles:
        points = by_vehicle.get(vehicle.id, [])
        if not points:
            continue
        result.append(
            {
                "vehicle_id": vehicle.id,
                "registration_number": vehicle.registration_number,
                "points": [
                    {
                        "latitude": point.latitude,
                        "longitude": point.longitude,
                        "speed_kph": point.speed_kph,
                        "recorded_at": point.recorded_at.isoformat() + "Z",
                    }
                    for point in points
                ],
                "is_simulated": points[-1].is_simulated,
            }
        )
    return result
