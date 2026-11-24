"""ORM -> API schema helpers.

Pydantic ``from_attributes`` covers most fields; these helpers handle computed
properties and permission lists consistently.
"""

from __future__ import annotations

from typing import Optional

from app.models import Driver, User, Vehicle
from app.schemas.auth import UserOut
from app.schemas.fleet import DriverOut, VehicleOut


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        job_title=user.job_title,
        organisation_id=user.organisation_id,
        is_active=user.is_active,
        is_verified=user.is_verified,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        phone_masked=user.phone_masked,
        permissions=sorted(user.permissions),
    )


def driver_out(driver: Driver) -> DriverOut:
    return DriverOut(
        id=driver.id,
        organisation_id=driver.organisation_id,
        user_id=driver.user_id,
        employee_id=driver.employee_id,
        first_name=driver.first_name,
        last_name=driver.last_name,
        full_name=driver.full_name,
        email=driver.email,
        phone_masked=driver.phone_masked,
        licence_number_masked=driver.licence_number_masked,
        licence_class=driver.licence_class,
        licence_expiry=driver.licence_expiry,
        status=driver.status,
        years_experience=driver.years_experience,
        training_hours=driver.training_hours,
        hire_date=driver.hire_date,
        city=driver.city,
        avatar_color=driver.avatar_color,
        assigned_vehicle_ids=driver.assigned_vehicle_ids,
        created_at=driver.created_at,
    )


def vehicle_out(vehicle: Vehicle) -> VehicleOut:
    return VehicleOut(
        id=vehicle.id,
        registration_number=vehicle.registration_number,
        vehicle_type=vehicle.vehicle_type,
        manufacturer=vehicle.manufacturer,
        model=vehicle.model,
        manufacturing_year=vehicle.manufacturing_year,
        fuel_type=vehicle.fuel_type,
        vin_masked=vehicle.vin_masked,
        assigned_driver_id=vehicle.assigned_driver_id,
        assigned_driver_name=vehicle.assigned_driver_name,
        gps_device_id=vehicle.gps_device_id,
        gps_device_serial=vehicle.gps_device_serial,
        status=vehicle.status,
        insurance_expiry=vehicle.insurance_expiry,
        mileage_km=vehicle.mileage_km,
        depot=vehicle.depot,
        notes=vehicle.notes,
        last_service_at=vehicle.last_service_at,
        next_service_km=vehicle.next_service_km,
        is_archived=vehicle.is_archived,
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at,
    )


def incident_out(incident, vehicle: Optional[Vehicle] = None):
    from app.schemas.safety import IncidentOut

    vehicle = vehicle or incident.vehicle
    return IncidentOut(
        id=incident.id,
        vehicle_id=incident.vehicle_id,
        registration_number=vehicle.registration_number if vehicle else None,
        driver_id=incident.driver_id,
        driver_name=incident.driver.full_name if incident.driver else None,
        reporter_id=incident.reporter_id,
        reporter_name=incident.reporter.full_name if incident.reporter else None,
        incident_type=incident.incident_type,
        title=incident.title,
        description=incident.description,
        severity=incident.severity,
        status=incident.status,
        latitude=incident.latitude,
        longitude=incident.longitude,
        occurred_at=incident.occurred_at,
        evidence=incident.evidence or [],
        investigation_notes=incident.investigation_notes,
        resolution_notes=incident.resolution_notes,
        emergency_contact=incident.emergency_contact_json or {},
        verified_at=incident.verified_at,
        resolved_at=incident.resolved_at,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )
