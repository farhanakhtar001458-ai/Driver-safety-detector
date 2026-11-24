"""Fleet, telemetry and location models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base
from app.models.enums import TelemetrySource, VehicleStatus
from app.models.identity import TimestampMixin


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("organisation_id", "registration_number", name="uq_vehicle_registration_per_org"),
        Index("ix_vehicles_org_status", "organisation_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    registration_number: Mapped[str] = mapped_column(String(32))
    vehicle_type: Mapped[str] = mapped_column(String(40))  # car, van, truck, bus, bike
    manufacturer: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(80))
    manufacturing_year: Mapped[int] = mapped_column(Integer)
    fuel_type: Mapped[str] = mapped_column(String(24), default="diesel")
    vin: Mapped[Optional[str]] = mapped_column(String(32))
    assigned_driver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drivers.id", ondelete="SET NULL"))
    gps_device_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "gps_devices.id",
            ondelete="SET NULL",
            # Breaks the vehicles <-> gps_devices cycle: the constraint is added
            # with ALTER TABLE after both tables exist, which keeps migrations
            # deterministic on PostgreSQL as well as SQLite.
            use_alter=True,
            name="fk_vehicles_gps_device_id",
        )
    )
    status: Mapped[str] = mapped_column(String(24), default=VehicleStatus.ACTIVE.value, index=True)
    insurance_expiry: Mapped[Optional[date]] = mapped_column(Date)
    mileage_km: Mapped[float] = mapped_column(Float, default=0.0)
    last_service_at: Mapped[Optional[date]] = mapped_column(Date)
    next_service_km: Mapped[Optional[float]] = mapped_column(Float)
    depot: Mapped[Optional[str]] = mapped_column(String(120))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    avatar_color: Mapped[str] = mapped_column(String(16), default="#0e7490")

    @property
    def assigned_driver_name(self) -> Optional[str]:
        return self.assigned_driver.full_name if self.assigned_driver else None

    @property
    def gps_device_serial(self) -> Optional[str]:
        return self.gps_device.serial_number if self.gps_device else None

    @property
    def vin_masked(self) -> Optional[str]:
        from app.core.security import mask_value

        return mask_value(self.vin, 4) if self.vin else None

    organisation = relationship("Organisation", back_populates="vehicles")
    assigned_driver: Mapped[Optional["Driver"]] = relationship(
        back_populates="assigned_vehicles", foreign_keys=[assigned_driver_id]
    )
    gps_device: Mapped[Optional["GPSDevice"]] = relationship(foreign_keys=[gps_device_id])
    locations: Mapped[list["VehicleLocation"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )
    trips: Mapped[list["Trip"]] = relationship(back_populates="vehicle")
    events: Mapped[list["DrivingEvent"]] = relationship(back_populates="vehicle")  # type: ignore[name-defined]


class Driver(TimestampMixin, Base):
    __tablename__ = "drivers"
    __table_args__ = (Index("ix_drivers_org_status", "organisation_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    employee_id: Mapped[Optional[str]] = mapped_column(String(40))
    first_name: Mapped[str] = mapped_column(String(60))
    last_name: Mapped[str] = mapped_column(String(60))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone_encrypted: Mapped[Optional[str]] = mapped_column(String(512))
    licence_number_encrypted: Mapped[Optional[str]] = mapped_column(String(512))
    licence_class: Mapped[Optional[str]] = mapped_column(String(40))
    licence_expiry: Mapped[Optional[date]] = mapped_column(Date)
    licence_issued: Mapped[Optional[date]] = mapped_column(Date)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    hire_date: Mapped[Optional[date]] = mapped_column(Date)
    address: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(80))
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(120))
    emergency_contact_phone_encrypted: Mapped[Optional[str]] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    years_experience: Mapped[int] = mapped_column(Integer, default=0)
    training_hours: Mapped[float] = mapped_column(Float, default=0.0)
    avatar_color: Mapped[str] = mapped_column(String(16), default="#7c3aed")

    organisation = relationship("Organisation", back_populates="drivers")
    user: Mapped[Optional["User"]] = relationship(foreign_keys=[user_id])  # type: ignore[name-defined]
    assigned_vehicles: Mapped[list["Vehicle"]] = relationship(
        back_populates="assigned_driver", foreign_keys="Vehicle.assigned_driver_id"
    )
    scores: Mapped[list["DriverScore"]] = relationship(back_populates="driver")  # type: ignore[name-defined]
    events: Mapped[list["DrivingEvent"]] = relationship(back_populates="driver")  # type: ignore[name-defined]
    incidents: Mapped[list["Incident"]] = relationship(back_populates="driver")  # type: ignore[name-defined]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def phone(self) -> Optional[str]:
        from app.core.security import decrypt_value

        return decrypt_value(self.phone_encrypted)

    @property
    def phone_masked(self) -> Optional[str]:
        from app.core.security import mask_value

        return mask_value(self.phone) if self.phone else None

    @property
    def licence_number(self) -> Optional[str]:
        from app.core.security import decrypt_value

        return decrypt_value(self.licence_number_encrypted)

    @property
    def licence_number_masked(self) -> Optional[str]:
        from app.core.security import mask_value

        return mask_value(self.licence_number, 4) if self.licence_number else None

    @property
    def emergency_contact_phone(self) -> Optional[str]:
        from app.core.security import decrypt_value

        return decrypt_value(self.emergency_contact_phone_encrypted)

    @property
    def assigned_vehicle_ids(self) -> list[int]:
        return [v.id for v in self.assigned_vehicles if not v.is_archived]


class GPSDevice(Base):
    __tablename__ = "gps_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"))
    serial_number: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    model: Mapped[Optional[str]] = mapped_column(String(60))
    provider: Mapped[Optional[str]] = mapped_column(String(60))
    key_hash: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="online")
    firmware: Mapped[Optional[str]] = mapped_column(String(30))
    installed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)



class VehicleLocation(Base):
    __tablename__ = "vehicle_locations"
    __table_args__ = (
        Index("ix_locations_vehicle_time", "vehicle_id", "recorded_at"),
        Index("ix_locations_org_time", "organisation_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("gps_devices.id", ondelete="SET NULL"))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    speed_kph: Mapped[float] = mapped_column(Float, default=0.0)
    heading: Mapped[float] = mapped_column(Float, default=0.0)
    accuracy_m: Mapped[float] = mapped_column(Float, default=8.0)
    altitude_m: Mapped[Optional[float]] = mapped_column(Float)
    odometer_km: Mapped[float] = mapped_column(Float, default=0.0)
    ignition_on: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(16), default=TelemetrySource.DEVICE.value)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="locations")


class Trip(TimestampMixin, Base):
    __tablename__ = "trips"
    __table_args__ = (Index("ix_trips_vehicle_start", "vehicle_id", "start_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    driver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drivers.id", ondelete="SET NULL"))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    start_latitude: Mapped[Optional[float]] = mapped_column(Float)
    start_longitude: Mapped[Optional[float]] = mapped_column(Float)
    end_latitude: Mapped[Optional[float]] = mapped_column(Float)
    end_longitude: Mapped[Optional[float]] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    duration_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    average_speed_kph: Mapped[float] = mapped_column(Float, default=0.0)
    max_speed_kph: Mapped[float] = mapped_column(Float, default=0.0)
    events_count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(16), default=TelemetrySource.DEVICE.value)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="trips")
    driver: Mapped[Optional["Driver"]] = relationship()


class Geofence(TimestampMixin, Base):
    __tablename__ = "geofences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    center_latitude: Mapped[float] = mapped_column(Float)
    center_longitude: Mapped[float] = mapped_column(Float)
    radius_meters: Mapped[float] = mapped_column(Float, default=500.0)
    alert_on_enter: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_on_exit: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class VehicleHealthReading(Base):
    __tablename__ = "vehicle_health_readings"
    __table_args__ = (Index("ix_health_vehicle_time", "vehicle_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    engine_temperature_c: Mapped[Optional[float]] = mapped_column(Float)
    battery_voltage: Mapped[Optional[float]] = mapped_column(Float)
    fuel_level_pct: Mapped[Optional[float]] = mapped_column(Float)
    fuel_consumption_l_per_100km: Mapped[Optional[float]] = mapped_column(Float)
    odometer_km: Mapped[float] = mapped_column(Float, default=0.0)
    fault_codes: Mapped[list] = mapped_column(default=list)
    health_score: Mapped[float] = mapped_column(Float, default=100.0)
    source: Mapped[str] = mapped_column(String(16), default=TelemetrySource.DEVICE.value)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
