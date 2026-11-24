"""Telemetry ingestion, trip assembly and event creation.

This module is the single write path for GPS data, whether it arrives from a
physical device or from the simulator. It keeps trip accounting consistent and
turns detected kinematic events into auditable records.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.models import (
    DrivingEvent,
    Driver,
    GPSDevice,
    Incident,
    Organisation,
    Trip,
    Vehicle,
    VehicleHealthReading,
    VehicleLocation,
)
from app.services.ai.rules_engine import (
    detect_events,
    get_thresholds,
    haversine_km,
    speed_limit_for,
)

STALE_TRIP_GAP = timedelta(minutes=20)


def _close_trip(db: Session, trip: Trip, end_time: datetime, lat: Optional[float], lng: Optional[float]) -> None:
    if trip.end_time is not None:
        return
    trip.end_time = end_time
    trip.end_latitude = lat
    trip.end_longitude = lng
    duration = max((end_time - trip.start_time).total_seconds() / 60.0, 1.0)
    trip.duration_minutes = round(duration, 1)
    trip.average_speed_kph = round(trip.distance_km / (duration / 60.0), 1) if duration else 0.0
    db.flush()


def _get_or_start_trip(
    db: Session, vehicle: Vehicle, when: datetime, lat: float, lng: float, source: str, simulated: bool
) -> Trip:
    trip = (
        db.query(Trip)
        .filter(Trip.vehicle_id == vehicle.id, Trip.end_time.is_(None))
        .order_by(Trip.start_time.desc())
        .first()
    )
    if trip:
        last_point = (
            db.query(VehicleLocation)
            .filter(VehicleLocation.vehicle_id == vehicle.id)
            .order_by(VehicleLocation.recorded_at.desc())
            .first()
        )
        if last_point and (when - last_point.recorded_at) > STALE_TRIP_GAP:
            _close_trip(db, trip, last_point.recorded_at, last_point.latitude, last_point.longitude)
            trip = None
    if not trip:
        trip = Trip(
            organisation_id=vehicle.organisation_id,
            vehicle_id=vehicle.id,
            driver_id=vehicle.assigned_driver_id,
            start_time=when,
            start_latitude=lat,
            start_longitude=lng,
            source=source,
            is_simulated=simulated,
        )
        db.add(trip)
        db.flush()
    return trip


def _create_event(
    db: Session,
    vehicle: Vehicle,
    trip: Optional[Trip],
    event: dict[str, Any],
    *,
    is_simulated: bool,
) -> DrivingEvent:
    record = DrivingEvent(
        organisation_id=vehicle.organisation_id,
        vehicle_id=vehicle.id,
        driver_id=vehicle.assigned_driver_id,
        trip_id=trip.id if trip else None,
        event_type=event["event_type"],
        severity=event["severity"],
        latitude=event.get("latitude"),
        longitude=event.get("longitude"),
        speed_kph=event.get("speed_kph"),
        speed_limit_kph=event.get("speed_limit_kph"),
        sensor_data=event.get("sensor_data", {}),
        recommended_action=event.get("recommended_action"),
        is_simulated=is_simulated,
        source=event.get("source", "simulated" if is_simulated else "device"),
        occurred_at=event.get("occurred_at") or datetime.utcnow(),
    )
    db.add(record)
    db.flush()
    if trip:
        trip.events_count = (trip.events_count or 0) + 1
    return record


def _maybe_create_incident(
    db: Session,
    vehicle: Vehicle,
    event: DrivingEvent,
    organisation: Organisation,
) -> Optional[Incident]:
    """A suspected collision creates an unverified incident, never an emergency dispatch."""
    incident = Incident(
        organisation_id=vehicle.organisation_id,
        vehicle_id=vehicle.id,
        driver_id=vehicle.assigned_driver_id,
        incident_type="collision_suspected",
        title=f"Possible collision detected - {vehicle.registration_number}",
        description=(
            "Automated flag from telemetry indicating an abrupt deceleration consistent with a possible impact. "
            "This is an unverified machine observation and requires human confirmation."
        ),
        severity="critical" if event.severity == "critical" else "severe",
        status="new",
        latitude=event.latitude,
        longitude=event.longitude,
        occurred_at=event.occurred_at,
        evidence=[
            {
                "type": "telemetry",
                "source": "simulated" if event.is_simulated else "device",
                "sensor_data": event.sensor_data,
                "note": "Unverified sensor observation",
            }
        ],
        emergency_contact_json={
            "note": "No emergency services are contacted automatically.",
            "verification_required": True,
        },
    )
    db.add(incident)
    db.flush()
    return incident


def record_point(
    db: Session,
    vehicle: Vehicle,
    point: dict[str, Any],
    *,
    source: str,
    is_simulated: bool,
    device: Optional[GPSDevice] = None,
) -> tuple[int, list[DrivingEvent]]:
    """Persist one telemetry point and any detected events."""
    when: datetime = point.get("recorded_at") or datetime.utcnow()
    lat = float(point["latitude"])
    lng = float(point["longitude"])
    speed = float(point.get("speed_kph") or 0.0)

    previous = (
        db.query(VehicleLocation)
        .filter(VehicleLocation.vehicle_id == vehicle.id)
        .order_by(VehicleLocation.recorded_at.desc())
        .first()
    )
    trip = _get_or_start_trip(db, vehicle, when, lat, lng, source, is_simulated)

    distance = 0.0
    if previous:
        distance = haversine_km(previous.latitude, previous.longitude, lat, lng)
        if distance < 50:  # ignore GPS jumps
            trip.distance_km = round((trip.distance_km or 0.0) + distance, 3)
            vehicle.mileage_km = round((vehicle.mileage_km or 0.0) + distance, 1)
    trip.driver_id = trip.driver_id or vehicle.assigned_driver_id
    trip.max_speed_kph = max(trip.max_speed_kph or 0.0, speed)

    location = VehicleLocation(
        organisation_id=vehicle.organisation_id,
        vehicle_id=vehicle.id,
        device_id=device.id if device else vehicle.gps_device_id,
        latitude=lat,
        longitude=lng,
        speed_kph=speed,
        heading=float(point.get("heading") or 0.0),
        accuracy_m=float(point.get("accuracy_m") or 8.0),
        altitude_m=point.get("altitude_m"),
        odometer_km=float(point.get("odometer_km") or vehicle.mileage_km or 0.0),
        ignition_on=bool(point.get("ignition_on", True)),
        source=source,
        is_simulated=is_simulated,
        recorded_at=when,
    )
    db.add(location)
    db.flush()

    created: list[DrivingEvent] = []
    organisation = db.get(Organisation, vehicle.organisation_id)
    thresholds = get_thresholds(organisation)
    if previous:
        prev_dict = {
            "latitude": previous.latitude,
            "longitude": previous.longitude,
            "speed_kph": previous.speed_kph,
            "heading": previous.heading,
            "recorded_at": previous.recorded_at,
        }
        detections = detect_events(
            prev_dict,
            {
                "latitude": lat,
                "longitude": lng,
                "speed_kph": speed,
                "heading": float(point.get("heading") or 0.0),
                "recorded_at": when,
                "source": source,
                "is_simulated": is_simulated,
            },
            thresholds,
            speed_limit_for(vehicle),
            vehicle.vehicle_type,
        )
        for detection in detections:
            event = _create_event(db, vehicle, trip, detection, is_simulated=is_simulated)
            created.append(event)
            if event.event_type == "harsh_braking" and event.severity == "critical":
                _maybe_create_incident(db, vehicle, event, organisation)  # type: ignore[arg-type]
    if device:
        device.last_seen_at = when
    return 1, created


def ingest_batch(
    db: Session,
    vehicle: Vehicle,
    points: Iterable[dict[str, Any]],
    *,
    source: str,
    is_simulated: bool,
    device: Optional[GPSDevice] = None,
) -> tuple[int, list[DrivingEvent]]:
    accepted = 0
    events: list[DrivingEvent] = []
    ordered = sorted(points, key=lambda item: item.get("recorded_at") or datetime.utcnow())
    for point in ordered:
        count, created = record_point(
            db, vehicle, point, source=source, is_simulated=is_simulated, device=device
        )
        accepted += count
        events.extend(created)
    return accepted, events


def close_stale_trips(db: Session, organisation_id: Optional[int] = None) -> int:
    """Close trips with no recent points; called periodically by the simulator."""
    now = datetime.utcnow()
    query = db.query(Trip).filter(Trip.end_time.is_(None))
    if organisation_id:
        query = query.filter(Trip.organisation_id == organisation_id)
    closed = 0
    for trip in query.all():
        last = (
            db.query(VehicleLocation)
            .filter(VehicleLocation.vehicle_id == trip.vehicle_id)
            .order_by(VehicleLocation.recorded_at.desc())
            .first()
        )
        if last and (now - last.recorded_at) > STALE_TRIP_GAP:
            _close_trip(db, trip, last.recorded_at, last.latitude, last.longitude)
            closed += 1
    db.flush()
    return closed


def record_health(
    db: Session,
    vehicle: Vehicle,
    *,
    engine_temperature_c: Optional[float] = None,
    battery_voltage: Optional[float] = None,
    fuel_level_pct: Optional[float] = None,
    fuel_consumption: Optional[float] = None,
    fault_codes: Optional[list[str]] = None,
    source: str = "device",
    is_simulated: bool = False,
    recorded_at: Optional[datetime] = None,
) -> VehicleHealthReading:
    """Store a diagnostic reading and compute a transparent health score."""
    score = 100.0
    faults = fault_codes or []
    if engine_temperature_c is not None:
        if engine_temperature_c > 115:
            score -= 25
        elif engine_temperature_c > 105:
            score -= 10
    if battery_voltage is not None:
        if battery_voltage < 11.8:
            score -= 25
        elif battery_voltage < 12.2:
            score -= 10
    if faults:
        score -= min(40, 12 * len(faults))
    score = round(max(0.0, min(100.0, score)), 1)
    reading = VehicleHealthReading(
        organisation_id=vehicle.organisation_id,
        vehicle_id=vehicle.id,
        engine_temperature_c=engine_temperature_c,
        battery_voltage=battery_voltage,
        fuel_level_pct=fuel_level_pct,
        fuel_consumption_l_per_100km=fuel_consumption,
        odometer_km=vehicle.mileage_km,
        fault_codes=faults,
        health_score=score,
        source=source,
        is_simulated=is_simulated,
        recorded_at=recorded_at or datetime.utcnow(),
    )
    db.add(reading)
    db.flush()
    return reading
