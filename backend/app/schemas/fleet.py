from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


def _upper(value: Optional[str]) -> Optional[str]:
    return value.strip().upper() if isinstance(value, str) else value


# --------------------------------------------------------------------------
# Vehicles
# --------------------------------------------------------------------------
class VehicleBase(BaseModel):
    registration_number: str = Field(min_length=3, max_length=32)
    vehicle_type: str = Field(max_length=40)
    manufacturer: str = Field(max_length=60)
    model: str = Field(max_length=80)
    manufacturing_year: int = Field(ge=1980, le=2027)
    fuel_type: str = Field(default="diesel", max_length=24)
    vin: Optional[str] = Field(default=None, max_length=32)
    assigned_driver_id: Optional[int] = None
    gps_device_id: Optional[int] = None
    status: str = "active"
    insurance_expiry: Optional[date] = None
    mileage_km: float = Field(default=0, ge=0)
    depot: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("registration_number")
    @classmethod
    def _registration(cls, value: str) -> str:
        value = value.strip().upper().replace(" ", "")
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("Registration number must contain letters and digits")
        return value

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        allowed = {"active", "inactive", "under_maintenance", "offline"}
        if value not in allowed:
            raise ValueError(f"Status must be one of {sorted(allowed)}")
        return value

    @field_validator("vin")
    @classmethod
    def _vin(cls, value: Optional[str]) -> Optional[str]:
        value = _upper(value)
        if value and (len(value) != 17 or not value.isalnum()):
            raise ValueError("VIN must be exactly 17 alphanumeric characters")
        return value


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    registration_number: Optional[str] = Field(default=None, min_length=3, max_length=32)
    vehicle_type: Optional[str] = Field(default=None, max_length=40)
    manufacturer: Optional[str] = Field(default=None, max_length=60)
    model: Optional[str] = Field(default=None, max_length=80)
    manufacturing_year: Optional[int] = Field(default=None, ge=1980, le=2027)
    fuel_type: Optional[str] = Field(default=None, max_length=24)
    vin: Optional[str] = Field(default=None, max_length=32)
    assigned_driver_id: Optional[int] = None
    gps_device_id: Optional[int] = None
    status: Optional[str] = None
    insurance_expiry: Optional[date] = None
    mileage_km: Optional[float] = Field(default=None, ge=0)
    depot: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("status")
    @classmethod
    def _status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {"active", "inactive", "under_maintenance", "offline"}
        if value not in allowed:
            raise ValueError(f"Status must be one of {sorted(allowed)}")
        return value

    @field_validator("vin")
    @classmethod
    def _vin(cls, value: Optional[str]) -> Optional[str]:
        value = _upper(value)
        if value and (len(value) != 17 or not value.isalnum()):
            raise ValueError("VIN must be exactly 17 alphanumeric characters")
        return value


class VehicleOut(ORMModel):
    id: int
    registration_number: str
    vehicle_type: str
    manufacturer: str
    model: str
    manufacturing_year: int
    fuel_type: str
    vin_masked: Optional[str] = None
    assigned_driver_id: Optional[int] = None
    assigned_driver_name: Optional[str] = None
    gps_device_id: Optional[int] = None
    gps_device_serial: Optional[str] = None
    status: str
    insurance_expiry: Optional[date] = None
    mileage_km: float
    depot: Optional[str] = None
    notes: Optional[str] = None
    last_service_at: Optional[date] = None
    next_service_km: Optional[float] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# Drivers
# --------------------------------------------------------------------------
class DriverBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=24)
    employee_id: Optional[str] = Field(default=None, max_length=40)
    licence_number: Optional[str] = Field(default=None, max_length=40)
    licence_class: Optional[str] = Field(default=None, max_length=40)
    licence_expiry: Optional[date] = None
    licence_issued: Optional[date] = None
    date_of_birth: Optional[date] = None
    hire_date: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    status: str = "active"
    years_experience: int = Field(default=0, ge=0, le=60)
    training_hours: float = Field(default=0, ge=0)
    user_id: Optional[int] = None

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        allowed = {"active", "inactive", "on_leave", "suspended"}
        if value not in allowed:
            raise ValueError(f"Status must be one of {sorted(allowed)}")
        return value


class DriverCreate(DriverBase):
    pass


class DriverUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    email: Optional[str] = None
    phone: Optional[str] = None
    employee_id: Optional[str] = None
    licence_number: Optional[str] = None
    licence_class: Optional[str] = None
    licence_expiry: Optional[date] = None
    licence_issued: Optional[date] = None
    date_of_birth: Optional[date] = None
    hire_date: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    status: Optional[str] = None
    years_experience: Optional[int] = Field(default=None, ge=0, le=60)
    training_hours: Optional[float] = Field(default=None, ge=0)
    user_id: Optional[int] = None


class DriverOut(ORMModel):
    id: int
    organisation_id: int
    user_id: Optional[int] = None
    employee_id: Optional[str] = None
    first_name: str
    last_name: str
    full_name: str
    email: Optional[str] = None
    phone_masked: Optional[str] = None
    licence_number_masked: Optional[str] = None
    licence_class: Optional[str] = None
    licence_expiry: Optional[date] = None
    status: str
    years_experience: int
    training_hours: float
    hire_date: Optional[date] = None
    city: Optional[str] = None
    avatar_color: str
    assigned_vehicle_ids: List[int] = Field(default_factory=list)
    created_at: datetime


# --------------------------------------------------------------------------
# Telemetry
# --------------------------------------------------------------------------
class GPSPointIn(BaseModel):
    device_serial: Optional[str] = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_kph: float = Field(default=0, ge=0, le=300)
    heading: float = Field(default=0, ge=0, le=360)
    accuracy_m: float = Field(default=8, ge=0, le=1000)
    altitude_m: Optional[float] = None
    odometer_km: float = Field(default=0, ge=0)
    ignition_on: bool = True
    recorded_at: Optional[datetime] = None
    fuel_level_pct: Optional[float] = Field(default=None, ge=0, le=100)
    engine_temperature_c: Optional[float] = Field(default=None, ge=-40, le=250)
    battery_voltage: Optional[float] = Field(default=None, ge=0, le=24)
    fault_codes: Optional[List[str]] = Field(default=None, max_length=10)


class GPSIngestRequest(BaseModel):
    vehicle_id: Optional[int] = None
    points: List[GPSPointIn] = Field(min_length=1, max_length=500)


class GPSIngestResponse(BaseModel):
    accepted: int
    events_created: int
    vehicle_id: Optional[int] = None
    simulated: bool = False


class LocationOut(ORMModel):
    id: int
    vehicle_id: int
    latitude: float
    longitude: float
    speed_kph: float
    heading: float
    accuracy_m: float
    odometer_km: float
    ignition_on: bool
    source: str
    is_simulated: bool
    recorded_at: datetime


class LiveVehicleOut(BaseModel):
    vehicle_id: int
    registration_number: str
    vehicle_type: str
    status: str
    driver_name: Optional[str] = None
    latitude: float
    longitude: float
    speed_kph: float
    heading: float
    ignition_on: bool
    last_seen: datetime
    is_simulated: bool
    today_distance_km: float = 0.0


class GeofenceIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=255)
    center_latitude: float = Field(ge=-90, le=90)
    center_longitude: float = Field(ge=-180, le=180)
    radius_meters: float = Field(default=500, gt=10, le=50000)
    alert_on_enter: bool = False
    alert_on_exit: bool = True
    is_active: bool = True


class GeofenceOut(ORMModel):
    id: int
    name: str
    description: Optional[str] = None
    center_latitude: float
    center_longitude: float
    radius_meters: float
    alert_on_enter: bool
    alert_on_exit: bool
    is_active: bool
    created_at: datetime


class TripOut(ORMModel):
    id: int
    vehicle_id: int
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    distance_km: float
    duration_minutes: float
    average_speed_kph: float
    max_speed_kph: float
    events_count: int
    source: str
    is_simulated: bool


class VehicleHealthOut(BaseModel):
    vehicle_id: int
    registration_number: str
    status: str
    health_score: float
    engine_temperature_c: Optional[float] = None
    battery_voltage: Optional[float] = None
    fuel_level_pct: Optional[float] = None
    fuel_consumption_l_per_100km: Optional[float] = None
    fault_codes: List[str] = Field(default_factory=list)
    mileage_km: float
    is_simulated: bool
    recorded_at: Optional[datetime] = None
    next_service_km: Optional[float] = None
    days_to_service: Optional[int] = None


class HealthReadingOut(ORMModel):
    id: int
    vehicle_id: int
    engine_temperature_c: Optional[float] = None
    battery_voltage: Optional[float] = None
    fuel_level_pct: Optional[float] = None
    fuel_consumption_l_per_100km: Optional[float] = None
    odometer_km: float
    fault_codes: List[str] = Field(default_factory=list)
    health_score: float
    source: str
    is_simulated: bool
    recorded_at: datetime


# --------------------------------------------------------------------------
# Maintenance
# --------------------------------------------------------------------------
class MaintenanceRecordIn(BaseModel):
    vehicle_id: int
    record_type: str = Field(default="service", max_length=40)
    title: str = Field(min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: str = "completed"
    odometer_km: float = Field(default=0, ge=0)
    cost: float = Field(default=0, ge=0)
    currency: str = Field(default="INR", max_length=8)
    performed_at: Optional[datetime] = None
    next_due_km: Optional[float] = Field(default=None, ge=0)
    next_due_date: Optional[datetime] = None
    vendor: Optional[str] = Field(default=None, max_length=120)

    @field_validator("record_type")
    @classmethod
    def _type(cls, value: str) -> str:
        allowed = {"service", "repair", "inspection", "tyre", "battery", "other"}
        if value not in allowed:
            raise ValueError(f"record_type must be one of {sorted(allowed)}")
        return value

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        allowed = {"scheduled", "in_progress", "completed", "overdue", "cancelled"}
        if value not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return value


class MaintenanceRecordOut(ORMModel):
    id: int
    vehicle_id: int
    record_type: str
    title: str
    description: Optional[str] = None
    status: str
    odometer_km: float
    cost: float
    currency: str
    performed_at: datetime
    next_due_km: Optional[float] = None
    next_due_date: Optional[datetime] = None
    vendor: Optional[str] = None
    created_at: datetime


class MaintenanceAlertOut(ORMModel):
    id: int
    vehicle_id: int
    registration_number: Optional[str] = None
    alert_type: str
    severity: str
    title: str
    description: Optional[str] = None
    status: str
    estimated_cost: Optional[float] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
