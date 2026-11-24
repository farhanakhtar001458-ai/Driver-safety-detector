"""Deterministic demo dataset.

Everything inserted here is demonstration data. Telemetry rows are flagged
``is_simulated=True`` and the UI shows a SIMULATED badge. No real person,
vehicle or accident record is represented.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import encrypt_value, hash_device_key, hash_password
from app.models import (
    AuditLog,
    Driver,
    DriverScore,
    DrivingEvent,
    Geofence,
    GPSDevice,
    Incident,
    MaintenanceAlert,
    MaintenanceRecord,
    Notification,
    Organisation,
    Payment,
    RoadHazard,
    RoadHotspot,
    Subscription,
    SubscriptionPlan,
    Trip,
    User,
    Vehicle,
    VehicleHealthReading,
    VehicleLocation,
)
from app.services.ai.scoring import compute_driver_scores

DEMO_PASSWORD = "Demo@12345"
SUPER_PASSWORD = "Super@12345"
DEVICE_KEY = "sw_demo_device_key_1234567890"

DRIVERS = [
    ("Rajesh", "Kumar", "MP09 2011 0012345", "rajesh@meridian.demo", "9876500001", 12, 8.0),
    ("Anjali", "Verma", "MP09 2014 0045612", "anjali@meridian.demo", "9876500002", 8, 6.5),
    ("Mohammed", "Irfan", "MP09 2009 0023456", "irfan@meridian.demo", "9876500003", 15, 4.0),
    ("Suresh", "Patil", "MP09 2016 0078901", "suresh@meridian.demo", "9876500004", 6, 5.0),
    ("Vikram", "Singh", "MP09 2012 0091234", "vikram@meridian.demo", "9876500005", 11, 3.5),
    ("Priya", "Nair", "MP09 2018 0034567", "priya@meridian.demo", "9876500006", 5, 7.0),
    ("Arjun", "Mehta", "MP09 2010 0056789", "arjun@meridian.demo", "9876500007", 14, 2.0),
    ("Deepak", "Yadav", "MP09 2017 0019876", "deepak@meridian.demo", "9876500008", 4, 6.0),
    ("Kavitha", "Reddy", "MP09 2013 0065432", "kavitha@meridian.demo", "9876500009", 9, 8.5),
    ("Sandeep", "Joshi", "MP09 2019 0087654", "sandeep@meridian.demo", "9876500010", 3, 9.0),
    ("Ramesh", "Gupta", "MP09 2008 0012347", "ramesh@meridian.demo", "9876500011", 17, 3.0),
    ("Farhan", "Sheikh", "MP09 2015 0043219", "farhan@meridian.demo", "9876500012", 7, 7.5),
]

VEHICLES = [
    ("MP09 AB 4211", "truck", "Tata", "Prima LX 2823", 2021, "diesel"),
    ("MP09 CD 7782", "truck", "Ashok Leyland", "AVTR 2820", 2022, "diesel"),
    ("MP09 EF 1290", "van", "Force Motors", "Traveller 3350", 2023, "diesel"),
    ("MP09 GH 5566", "van", "Maruti Suzuki", "Eeco Cargo", 2022, "petrol"),
    ("MP09 JK 9034", "car", "Toyota", "Innova Crysta", 2023, "diesel"),
    ("MP09 LM 2245", "car", "Maruti Suzuki", "Swift Dzire", 2021, "petrol"),
    ("MP09 NP 6678", "bus", "Tata", "Starbus LP 410", 2020, "diesel"),
    ("MP09 QR 3311", "truck", "BharatBenz", "2823C", 2022, "diesel"),
    ("MP09 ST 8850", "car", "Hyundai", "Creta", 2023, "petrol"),
    ("MP09 UV 1142", "van", "Mahindra", "Bolero Pickup", 2021, "diesel"),
    ("MP09 WX 7723", "car", "Tata", "Altroz", 2022, "petrol"),
    ("MP09 YZ 9910", "bus", "Ashok Leyland", "MiTR", 2021, "diesel"),
]


def _seed_users(db: Session, org: Organisation) -> dict[str, User]:
    users: dict[str, User] = {}

    def add(email: str, password: str, full_name: str, role: str, job_title: str | None = None) -> User:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            users[email] = existing
            return existing
        user = User(
            organisation_id=org.id,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            job_title=job_title,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.flush()
        users[email] = user
        return user

    add("admin@meridian.demo", DEMO_PASSWORD, "Aditi Sharma", "org_admin", "Operations Director")
    add("fleet@meridian.demo", DEMO_PASSWORD, "Rohan Mehta", "fleet_manager", "Fleet Manager")
    add("safety@meridian.demo", DEMO_PASSWORD, "Neha Kulkarni", "safety_officer", "Safety Officer")
    add("rajesh@meridian.demo", DEMO_PASSWORD, "Rajesh Kumar", "driver", "Driver")
    add("anjali@meridian.demo", DEMO_PASSWORD, "Anjali Verma", "driver", "Driver")
    return users


def _seed_subscription(db: Session, org: Organisation) -> Subscription:
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "professional").first()
    now = datetime.utcnow()
    subscription = Subscription(
        organisation_id=org.id,
        plan_id=plan.id if plan else 1,
        status="active",
        seats=3,
        trial_start=now - timedelta(days=45),
        trial_end=now - timedelta(days=31),
        current_period_start=now - timedelta(days=10),
        current_period_end=now + timedelta(days=20),
    )
    db.add(subscription)
    db.flush()
    for index, (amount, status, days_ago) in enumerate(
        [(3499 * 3, "succeeded", 40), (3499 * 3, "succeeded", 10), (3499 * 3, "pending", 0)]
    ):
        db.add(
            Payment(
                organisation_id=org.id,
                subscription_id=subscription.id,
                invoice_number=f"INV-2026{index + 1:02d}-{org.id:04d}-{index + 1:03d}",
                amount=amount,
                currency="INR",
                status=status,
                provider="manual",
                description="Professional plan - 3 seats",
                paid_at=now - timedelta(days=days_ago) if status == "succeeded" else None,
            )
        )
    db.flush()
    return subscription


def _seed_vehicles(db: Session, org: Organisation) -> tuple[list[Vehicle], list[Driver]]:
    drivers: list[Driver] = []
    for index, (first, last, licence, email, phone, years, training) in enumerate(DRIVERS):
        expiry_days = 18 if index in {3, 7} else random.randint(120, 900)
        driver = Driver(
            organisation_id=org.id,
            user_id=None,
            employee_id=f"EMP-{1001 + index}",
            first_name=first,
            last_name=last,
            email=email,
            phone_encrypted=encrypt_value(phone),
            licence_number_encrypted=encrypt_value(licence),
            licence_class="HMV" if index < 4 else "LMV",
            licence_expiry=date.today() + timedelta(days=expiry_days),
            licence_issued=date.today() - timedelta(days=365 * years + 120),
            date_of_birth=date(1985 + (index % 10), (index % 12) + 1, (index % 25) + 2),
            hire_date=date.today() - timedelta(days=365 * (years // 2 + 1)),
            address=f"{12 + index}_demo_street, Arera Colony",
            city="Bhopal",
            emergency_contact_name=f"Emergency contact {index + 1}",
            emergency_contact_phone_encrypted=encrypt_value(f"9765{index:06d}"),
            status="active",
            years_experience=years,
            training_hours=training,
        )
        db.add(driver)
        db.flush()
        drivers.append(driver)

    vehicles: list[Vehicle] = []
    for index, (registration, vehicle_type, manufacturer, model, year, fuel) in enumerate(VEHICLES):
        vehicle = Vehicle(
            organisation_id=org.id,
            registration_number=registration,
            vehicle_type=vehicle_type,
            manufacturer=manufacturer,
            model=model,
            manufacturing_year=year,
            fuel_type=fuel,
            vin=None,
            assigned_driver_id=drivers[index].id if index < len(drivers) else None,
            status="active" if index < 9 else ("under_maintenance" if index == 9 else "offline"),
            insurance_expiry=date.today() + timedelta(days=random.randint(45, 400)),
            mileage_km=(mileage := round(random.uniform(28000, 186000), 1)),
            depot="Bhopal Central Depot",
            # Most vehicles are not overdue; two are deliberately overdue so the
            # maintenance queue has something realistic to show.
            next_service_km=(
                round(mileage - random.uniform(500, 3000), 0)
                if index % 6 == 3
                else round(mileage + random.uniform(2000, 12000), 0)
            ),
        )
        if index % 3 == 0:
            vehicle.vin = "MH" + str(2020 + index % 5) + "DEMO" + str(100000 + index * 137)
        db.add(vehicle)
        db.flush()
        vehicles.append(vehicle)

    # Link driver accounts for two demo drivers.
    for email, driver in (("rajesh@meridian.demo", drivers[0]), ("anjali@meridian.demo", drivers[1])):
        user = db.query(User).filter(User.email == email).first()
        if user:
            driver.user_id = user.id

    # GPS devices
    for index, vehicle in enumerate(vehicles[:10]):
        device = GPSDevice(
            organisation_id=org.id,
            vehicle_id=vehicle.id,
            serial_number=f"SW-GPS-{1001 + index}",
            model="SW TrackPro 4G",
            provider="SafeWay Telematics (demo)",
            key_hash=hash_device_key(DEVICE_KEY) if index == 0 else None,
            status="online" if index < 8 else "offline",
            firmware="2.4.1",
            installed_at=datetime.utcnow() - timedelta(days=300 - index * 12),
            last_seen_at=datetime.utcnow() - timedelta(minutes=index * 7),
        )
        db.add(device)
        db.flush()
        vehicle.gps_device_id = device.id
    db.flush()
    return vehicles, drivers


def _seed_geofences(db: Session, org: Organisation) -> None:
    fences = [
        ("Bhopal Depot Zone", 23.2360, 77.4010, 1200, "Operational depot geofence"),
        ("Airport Corridor", 23.2870, 77.3370, 2500, "High-speed corridor"),
        ("Kolar Industrial Area", 23.2100, 77.3660, 1800, "Industrial estate"),
    ]
    for name, lat, lng, radius, description in fences:
        db.add(
            Geofence(
                organisation_id=org.id,
                name=name,
                description=description,
                center_latitude=lat,
                center_longitude=lng,
                radius_meters=radius,
                alert_on_enter=False,
                alert_on_exit=True,
            )
        )
    db.flush()


EVENT_TYPES = [
    "speeding", "harsh_braking", "rapid_acceleration", "aggressive_cornering",
    "excessive_duration", "seatbelt_violation", "possible_distraction",
]
EVENT_WEIGHTS = [0.34, 0.22, 0.14, 0.12, 0.08, 0.06, 0.04]
EVENT_LABELS = {
    "speeding": "Speeding",
    "harsh_braking": "Harsh braking",
    "rapid_acceleration": "Rapid acceleration",
    "aggressive_cornering": "Aggressive cornering",
    "excessive_duration": "Excessive driving duration",
    "seatbelt_violation": "Seatbelt non-compliance",
    "possible_distraction": "Possible distraction",
}
ACTIONS = {
    "speeding": "Follow the posted speed limit and use cruise control where safe.",
    "harsh_braking": "Increase following distance and anticipate signals early.",
    "rapid_acceleration": "Accelerate smoothly and avoid full-throttle starts.",
    "aggressive_cornering": "Reduce speed before corners and avoid braking mid-turn.",
    "excessive_duration": "Take a break at least every 4.5 hours of continuous driving.",
    "seatbelt_violation": "Confirm the seatbelt is fastened before moving off.",
    "possible_distraction": "Review the flagged moment with a supervisor; keep devices stowed.",
}


def _event_sensor(event_type: str, speed: float, limit: float, rng: random.Random) -> dict:
    if event_type == "speeding":
        return {
            "measured_speed_kph": round(speed, 1),
            "limit_kph": limit,
            "excess_kph": round(speed - limit, 1),
            "sample_interval_s": 3,
        }
    if event_type == "harsh_braking":
        decel = round(rng.uniform(3.2, 6.4), 2)
        return {
            "deceleration_mps2": decel,
            "speed_before_kph": round(speed + rng.uniform(15, 35), 1),
            "speed_after_kph": round(speed, 1),
            "sample_interval_s": 3,
        }
    if event_type == "rapid_acceleration":
        return {
            "acceleration_mps2": round(rng.uniform(2.6, 4.8), 2),
            "speed_before_kph": round(max(0, speed - 25), 1),
            "speed_after_kph": round(speed, 1),
        }
    if event_type == "aggressive_cornering":
        return {
            "lateral_acceleration_mps2": round(rng.uniform(3.1, 5.4), 2),
            "heading_change_deg": round(rng.uniform(25, 80), 1),
            "speed_kph": round(speed, 1),
        }
    if event_type == "excessive_duration":
        return {"continuous_driving_hours": round(rng.uniform(4.6, 7.2), 2)}
    if event_type == "seatbelt_violation":
        return {"seatbelt_fastened": False, "source": "vehicle_sensor", "verified": False}
    return {
        "observation": "head_movement_pattern",
        "confidence": round(rng.uniform(0.45, 0.68), 2),
        "camera_authorised": True,
        "note": "Low-confidence observation - requires human review",
    }


def _seed_history(db: Session, org: Organisation, vehicles: list[Vehicle], drivers: list[Driver]) -> None:
    rng = random.Random(42)
    now = datetime.utcnow()
    locations: list[VehicleLocation] = []
    events: list[DrivingEvent] = []

    for index, driver in enumerate(drivers):
        vehicle = vehicles[index] if index < len(vehicles) else vehicles[0]
        risk_profile = 0.35 + (index % 5) * 0.16  # 0.35 .. 0.99
        # Trips: roughly 2-4 per week for 90 days.
        for week in range(13):
            for trip_index in range(rng.randint(2, 4)):
                start = now - timedelta(days=week * 7 + rng.randint(0, 6), hours=rng.randint(5, 18))
                distance = round(rng.uniform(45, 210), 1)
                duration = round(distance / rng.uniform(38, 62) * 60, 1)
                trip = Trip(
                    organisation_id=org.id,
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    start_time=start,
                    end_time=start + timedelta(minutes=duration),
                    start_latitude=23.2 + rng.uniform(-0.08, 0.08),
                    start_longitude=77.35 + rng.uniform(-0.08, 0.08),
                    end_latitude=23.2 + rng.uniform(-0.08, 0.08),
                    end_longitude=77.35 + rng.uniform(-0.08, 0.08),
                    distance_km=distance,
                    duration_minutes=duration,
                    average_speed_kph=round(distance / (duration / 60), 1),
                    max_speed_kph=round(rng.uniform(55, 112), 1),
                    events_count=0,
                    source="simulated",
                    is_simulated=True,
                )
                db.add(trip)
                db.flush()

                # Events attached to this trip.
                # Real fleets see roughly 1-3 safety events per 100 km. Keeping the
                # mean low also stops the risk model from saturating at "critical"
                # for every driver, which would make the demo meaningless.
                count = int(rng.gauss(0.35 + risk_profile * 1.5, 1.1))
                count = max(0, min(5, count))
                for event_index in range(count):
                    event_type = rng.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=1)[0]
                    if event_type == "excessive_duration" and duration < 270:
                        event_type = "speeding"
                    limit = 55 if vehicle.vehicle_type in {"truck", "bus"} else 60
                    speed = limit + rng.uniform(6, 34) if event_type == "speeding" else rng.uniform(22, 88)
                    severity_choices = ["low", "medium", "high", "critical"]
                    severity_weights = (
                        [0.35, 0.38, 0.2, 0.07]
                        if risk_profile < 0.6
                        else [0.22, 0.34, 0.3, 0.14]
                    )
                    severity = rng.choices(severity_choices, weights=severity_weights, k=1)[0]
                    occurred = start + timedelta(minutes=rng.uniform(5, max(10, duration - 5)))
                    lat = 23.2 + rng.uniform(-0.09, 0.09)
                    lng = 77.35 + rng.uniform(-0.09, 0.09)
                    event = DrivingEvent(
                        organisation_id=org.id,
                        vehicle_id=vehicle.id,
                        driver_id=driver.id,
                        trip_id=trip.id,
                        event_type=event_type,
                        severity=severity,
                        latitude=lat,
                        longitude=lng,
                        speed_kph=round(speed, 1),
                        speed_limit_kph=limit,
                        sensor_data=_event_sensor(event_type, speed, limit, rng),
                        recommended_action=ACTIONS[event_type],
                        is_simulated=True,
                        source="simulated",
                        occurred_at=occurred,
                    )
                    db.add(event)
                    events.append(event)
                    trip.events_count += 1

        # Score history for each week.
        for week in range(8):
            period_start = (now - timedelta(days=now.weekday() + 7 * (week + 1))).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            period_end = period_start + timedelta(days=7)
            week_events = [e for e in events if e.driver_id == driver.id and period_start <= e.occurred_at < period_end]
            week_distance = sum(
                float(t.distance_km)
                for t in db.query(Trip).filter(
                    Trip.driver_id == driver.id, Trip.start_time >= period_start, Trip.start_time < period_end
                ).all()
            )
            base = 96 - risk_profile * 38 + rng.uniform(-4, 4)
            base += week * 0.6  # gradual improvement trend
            score_value = round(max(35, min(99, base)), 1)
            db.add(
                DriverScore(
                    organisation_id=org.id,
                    driver_id=driver.id,
                    period="weekly",
                    period_start=period_start,
                    period_end=period_end,
                    overall_score=score_value,
                    speed_score=round(max(20, min(100, score_value + rng.uniform(-6, 4))), 1),
                    braking_score=round(max(20, min(100, score_value + rng.uniform(-5, 6))), 1),
                    acceleration_score=round(max(20, min(100, score_value + rng.uniform(-4, 7))), 1),
                    cornering_score=round(max(20, min(100, score_value + rng.uniform(-5, 5))), 1),
                    seatbelt_score=round(max(30, min(100, score_value + rng.uniform(-3, 6))), 1),
                    consistency_score=round(max(20, min(100, score_value + rng.uniform(-7, 4))), 1),
                    events_count=len(week_events),
                    distance_km=round(week_distance, 1),
                    confidence=0.78,
                    breakdown={"source": "demo_seed", "events": len(week_events)},
                    model_version="score-exp-1.1.0",
                )
            )
    db.flush()

    # Recent route history (last 2 hours) for live map trails.
    for index, vehicle in enumerate(vehicles[:6]):
        route_points = [
            (23.2 + 0.03 * (index % 3), 77.38 + 0.02 * (index % 2)),
            (23.22 + 0.02 * (index % 3), 77.40),
            (23.25, 77.42),
            (23.24, 77.44),
            (23.22, 77.43),
        ]
        for step in range(24):
            position = route_points[step % len(route_points)]
            recorded = now - timedelta(minutes=(24 - step) * 5)
            locations.append(
                VehicleLocation(
                    organisation_id=org.id,
                    vehicle_id=vehicle.id,
                    device_id=vehicle.gps_device_id,
                    latitude=position[0] + rng.uniform(-0.002, 0.002),
                    longitude=position[1] + rng.uniform(-0.002, 0.002),
                    speed_kph=round(rng.uniform(18, 72), 1),
                    heading=round(rng.uniform(0, 359), 1),
                    accuracy_m=round(rng.uniform(3, 9), 1),
                    odometer_km=vehicle.mileage_km,
                    ignition_on=True,
                    source="simulated",
                    is_simulated=True,
                    recorded_at=recorded,
                )
            )
    db.add_all(locations)
    db.flush()


def _seed_incidents(db: Session, org: Organisation, vehicles: list[Vehicle], drivers: list[Driver], admin: User, safety: User) -> None:
    now = datetime.utcnow()
    incidents = [
        ("Possible collision detected - MP09 AB 4211", 0, 0, "collision_suspected", "critical", "under_investigation", 2),
        ("Harsh braking near MP Nagar junction", 1, 1, "harsh_event", "moderate", "verified", 4),
        ("Near miss reported on Airport Corridor", 2, 2, "near_miss", "severe", "new", 1),
        ("Vehicle breakdown - cooling fault", 9, 9, "breakdown", "minor", "resolved", 9),
        ("Geofence exit without authorisation", 4, 4, "geofence_breach", "minor", "false_alert", 12),
        ("Rear-end near miss at signal", 5, 5, "near_miss", "moderate", "resolved", 18),
        ("Tyre burst on Kolar Road", 3, 3, "breakdown", "severe", "verified", 6),
    ]
    for title, vehicle_index, driver_index, incident_type, severity, status, days_ago in incidents:
        db.add(
            Incident(
                organisation_id=org.id,
                vehicle_id=vehicles[vehicle_index].id,
                driver_id=drivers[driver_index].id,
                reporter_id=admin.id,
                incident_type=incident_type,
                title=title,
                description=(
                    "Demo incident record created for workflow demonstration. Evidence entries are illustrative "
                    "and must be replaced with verified material in production."
                ),
                severity=severity,
                status=status,
                latitude=23.23 + random.Random(days_ago).uniform(-0.03, 0.03),
                longitude=77.40 + random.Random(days_ago + 1).uniform(-0.03, 0.03),
                occurred_at=now - timedelta(days=days_ago, hours=3),
                evidence=[
                    {"type": "telemetry", "note": "Simulated telemetry snapshot", "verified": False},
                    {"type": "photo", "note": "Photo placeholder (demo)", "verified": False},
                ],
                investigation_notes="Reviewed by safety officer. No injuries reported." if status in {"verified", "resolved"} else None,
                resolution_notes="Closed after driver coaching session." if status == "resolved" else None,
                verified_by_id=safety.id if status in {"verified", "resolved"} else None,
                resolved_by_id=safety.id if status == "resolved" else None,
                resolved_at=now - timedelta(days=max(0, days_ago - 2)) if status == "resolved" else None,
                emergency_contact_json={
                    "name": "Demo Emergency Contact",
                    "phone": "+91 98765 00000",
                    "note": "Demo data. Emergency services are never contacted automatically.",
                },
            )
        )
    db.flush()


def _seed_maintenance(db: Session, org: Organisation, vehicles: list[Vehicle], admin: User) -> None:
    now = datetime.utcnow()
    record_types = ["service", "repair", "inspection", "tyre", "battery"]
    for index, vehicle in enumerate(vehicles):
        for record_index in range(2):
            performed = now - timedelta(days=30 + record_index * 55 + index * 3)
            db.add(
                MaintenanceRecord(
                    organisation_id=org.id,
                    vehicle_id=vehicle.id,
                    record_type=record_types[(index + record_index) % len(record_types)],
                    title=f"Periodic maintenance - {vehicle.registration_number}",
                    description="Demo maintenance record with simulated cost and odometer values.",
                    status="completed",
                    odometer_km=max(1000, vehicle.mileage_km - random.uniform(500, 9000)),
                    cost=round(random.uniform(1800, 18500), 2),
                    currency="INR",
                    performed_at=performed,
                    next_due_km=round(vehicle.mileage_km + random.uniform(5000, 12000), 0),
                    next_due_date=performed + timedelta(days=180),
                    vendor="Demo Auto Service, Bhopal",
                    created_by_id=admin.id,
                )
            )
        # Latest health reading.
        fault_codes = []
        if index in {2, 7}:
            fault_codes = ["P0300"]
        if index == 9:
            fault_codes = ["P0420", "B1234"]
        db.add(
            VehicleHealthReading(
                organisation_id=org.id,
                vehicle_id=vehicle.id,
                engine_temperature_c=round(random.uniform(84, 104), 1),
                battery_voltage=round(random.uniform(11.9, 13.8), 2),
                fuel_level_pct=round(random.uniform(28, 92), 1),
                fuel_consumption_l_per_100km=round(random.uniform(6.5, 18.0), 1),
                odometer_km=vehicle.mileage_km,
                fault_codes=fault_codes,
                health_score=round(max(42, 100 - len(fault_codes) * 14 - random.uniform(0, 12)), 1),
                source="simulated",
                is_simulated=True,
                recorded_at=now - timedelta(hours=random.uniform(1, 20)),
            )
        )
    db.flush()

    alerts = [
        (0, "service_due", "medium", "Service due in 1,200 km", "Vehicle is approaching its next service interval."),
        (2, "fault_code", "high", "Engine misfire code P0300", "Diagnostic trouble code reported by the ECU. Inspect ignition system."),
        (9, "predictive", "medium", "Battery voltage trend below threshold", "Voltage has declined over the last 14 days; battery testing recommended."),
        (7, "fault_code", "high", "Catalyst efficiency below threshold (P0420)", "Emissions performance below expected range."),
        (4, "insurance", "low", "Insurance expires in 45 days", "Renewal reminder for comprehensive coverage."),
        (11, "service_due", "high", "Overdue service - 3,400 km past interval", "Vehicle has exceeded its service interval."),
        (3, "tyre", "medium", "Tyre tread approaching limit", "Front tyres measured close to the legal tread limit."),
        (5, "brake", "high", "Brake pad wear sensor alert", "Brake pads require inspection before the next long journey."),
    ]
    for vehicle_index, alert_type, severity, title, description in alerts:
        db.add(
            MaintenanceAlert(
                organisation_id=org.id,
                vehicle_id=vehicles[vehicle_index].id,
                alert_type=alert_type,
                severity=severity,
                title=title,
                description=description,
                status="open",
                estimated_cost=round(random.uniform(800, 12000), 2) if alert_type != "insurance" else None,
            )
        )
    db.flush()


def _seed_notifications(db: Session, org: Organisation, users: dict[str, User]) -> None:
    now = datetime.utcnow()
    admin = users.get("admin@meridian.demo")
    fleet = users.get("fleet@meridian.demo")
    safety = users.get("safety@meridian.demo")
    entries = [
        (admin, "possible_accident", "Possible collision requires verification", "Telemetry flagged an abrupt deceleration on MP09 AB 4211. Verify driver safety before recording an outcome.", "urgent", 2),
        (admin, "maintenance_reminder", "Service due on MP09 GH 5566", "Next service is due in 1,200 km. Schedule a workshop slot.", "medium", 26),
        (fleet, "speeding_alert", "Repeated speeding events", "Three drivers recorded speeding on more than 3 days this week.", "high", 4),
        (safety, "incident_update", "Incident moved to Under Investigation", "Possible collision on MP09 AB 4211 is now under investigation.", "high", 3),
        (admin, "licence_expiry", "Two licences expire within 30 days", "Suresh Patil and Deepak Yadav need licence renewal before expiry.", "medium", 30),
        (fleet, "vehicle_offline", "MP09 YZ 9910 offline", "No telemetry received for more than 60 minutes.", "medium", 12),
        (safety, "driver_safety_warning", "Coaching recommended for 2 drivers", "Safety score below 70 for two consecutive weeks.", "medium", 40),
        (admin, "system", "Weekly safety report ready", "The weekly safety report has been generated and is available in Reports.", "low", 60),
    ]
    for user, notification_type, title, message, priority, minutes_ago in entries:
        if not user:
            continue
        db.add(
            Notification(
                organisation_id=org.id,
                user_id=user.id,
                type=notification_type,
                title=title,
                message=message,
                priority=priority,
                channel="in_app",
                delivery_status="delivered",
                related_type="incident" if "accident" in notification_type else None,
                related_id=1 if "accident" in notification_type else None,
                created_at=now - timedelta(minutes=minutes_ago),
            )
        )
    db.flush()


def _seed_audit(db: Session, org: Organisation, users: dict[str, User]) -> None:
    admin = users.get("admin@meridian.demo")
    actions = [
        ("auth.login", "session", "Signed in"),
        ("vehicle.create", "vehicle", "Registered MP09 AB 4211"),
        ("driver.create", "driver", "Added driver Rajesh Kumar"),
        ("incident.status_change", "incident", "Moved incident to under_investigation"),
        ("report.generate", "report", "Generated weekly safety report"),
        ("settings.update", "organisation", "Updated monitoring policy"),
        ("subscription.upgrade", "subscription", "Upgraded to Professional plan"),
        ("risk.assess", "risk", "Ran fleet risk assessment"),
    ]
    for index, (action, resource_type, detail) in enumerate(actions):
        db.add(
            AuditLog(
                organisation_id=org.id,
                user_id=admin.id if admin else None,
                action=action,
                resource_type=resource_type,
                resource_id=str(index + 1),
                detail={"summary": detail, "source": "demo_seed"},
                ip_address="127.0.0.1",
                user_agent="seed",
                created_at=datetime.utcnow() - timedelta(hours=index * 7 + 2),
            )
        )
    db.flush()


def _seed_road_safety(db: Session, org: Organisation) -> None:
    hotspots = [
        (23.2330, 77.4100, "MP Nagar junction (demo)", "high", 18),
        (23.2870, 77.3370, "Airport approach (demo)", "medium", 11),
        (23.2100, 77.3660, "Kolar industrial belt (demo)", "medium", 9),
        (23.2450, 77.4200, "Habibganj station road (demo)", "high", 14),
        (23.2000, 77.3600, "Kolar Road curve (demo)", "medium", 7),
        (23.2700, 77.4400, "Raisen Road stretch (demo)", "low", 4),
    ]
    for lat, lng, label, severity, count in hotspots:
        db.add(
            RoadHotspot(
                organisation_id=org.id,
                latitude=lat,
                longitude=lng,
                label=label,
                severity=severity,
                radius_meters=420,
                historical_count=count,
                source_name="Illustrative demo dataset - not official accident statistics",
                is_illustrative=True,
                notes="Placeholder hotspot for demonstrating the heat-map visualisation.",
            )
        )
    hazards = [
        (23.2401, 77.4120, "pothole", "medium", "Pothole reported on service road", 12),
        (23.2610, 77.3901, "fog", "high", "Reduced visibility in early morning", 6),
        (23.2150, 77.3700, "construction", "medium", "Lane closure for metro work", 48),
        (23.2800, 77.4450, "flooding", "high", "Water logging after heavy rain", 10),
    ]
    for lat, lng, hazard_type, severity, description, hours in hazards:
        db.add(
            RoadHazard(
                organisation_id=org.id,
                latitude=lat,
                longitude=lng,
                hazard_type=hazard_type,
                severity=severity,
                description=description,
                status="active",
                expires_at=datetime.utcnow() + timedelta(hours=hours),
                is_simulated=True,
            )
        )
    db.flush()


def seed_demo_data(db: Session) -> None:
    if db.query(Organisation).filter(Organisation.slug == "meridian-logistics").first():
        return

    org = Organisation(
        name="Meridian Logistics",
        slug="meridian-logistics",
        billing_email="billing@meridian.demo",
        phone="+91 98765 00000",
        address="12_demo_street, Arera Colony",
        city="Bhopal",
        country="India",
        timezone="Asia/Kolkata",
        monitoring_policy_accepted_at=datetime.utcnow(),
        settings_json={"demo": True},
    )
    db.add(org)
    db.flush()

    # Super admin is a platform-level account with no organisation.
    if not db.query(User).filter(User.email == "superadmin@safeway.demo").first():
        db.add(
            User(
                email="superadmin@safeway.demo",
                password_hash=hash_password(SUPER_PASSWORD),
                full_name="Platform Administrator",
                role="super_admin",
                is_active=True,
                is_verified=True,
            )
        )
        db.flush()

    users = _seed_users(db, org)
    _seed_subscription(db, org)
    vehicles, drivers = _seed_vehicles(db, org)
    _seed_geofences(db, org)
    _seed_history(db, org, vehicles, drivers)
    _seed_incidents(db, org, vehicles, drivers, users["admin@meridian.demo"], users["safety@meridian.demo"])
    _seed_maintenance(db, org, vehicles, users["admin@meridian.demo"])
    _seed_notifications(db, org, users)
    _seed_audit(db, org, users)
    _seed_road_safety(db, org)

    db.commit()
