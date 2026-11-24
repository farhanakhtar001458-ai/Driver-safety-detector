"""Safety, behaviour, incident and notification models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base
from app.models.identity import TimestampMixin


class DrivingEvent(TimestampMixin, Base):
    __tablename__ = "driving_events"
    __table_args__ = (
        Index("ix_events_org_time", "organisation_id", "occurred_at"),
        Index("ix_events_driver_time", "driver_id", "occurred_at"),
        Index("ix_events_vehicle_time", "vehicle_id", "occurred_at"),
        Index("ix_events_type_severity", "event_type", "severity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    driver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drivers.id", ondelete="SET NULL"), index=True)
    trip_id: Mapped[Optional[int]] = mapped_column(ForeignKey("trips.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    speed_kph: Mapped[Optional[float]] = mapped_column(Float)
    speed_limit_kph: Mapped[Optional[float]] = mapped_column(Float)
    sensor_data: Mapped[dict] = mapped_column(default=dict)
    recommended_action: Mapped[Optional[str]] = mapped_column(String(255))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(16), default="device")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    vehicle = relationship("Vehicle", back_populates="events")
    driver = relationship("Driver", back_populates="events")


class DriverScore(TimestampMixin, Base):
    __tablename__ = "driver_scores"
    __table_args__ = (
        Index("ix_scores_driver_period", "driver_id", "period", "period_start"),
        UniqueConstraint("driver_id", "period", "period_start", name="uq_score_driver_period_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(16), default="weekly")  # daily|weekly|monthly|overall
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    overall_score: Mapped[float] = mapped_column(Float)
    speed_score: Mapped[float] = mapped_column(Float, default=100.0)
    braking_score: Mapped[float] = mapped_column(Float, default=100.0)
    acceleration_score: Mapped[float] = mapped_column(Float, default=100.0)
    cornering_score: Mapped[float] = mapped_column(Float, default=100.0)
    seatbelt_score: Mapped[Optional[float]] = mapped_column(Float)
    consistency_score: Mapped[float] = mapped_column(Float, default=100.0)
    events_count: Mapped[int] = mapped_column(Integer, default=0)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    breakdown: Mapped[dict] = mapped_column(default=dict)
    model_version: Mapped[str] = mapped_column(String(40), default="score-exp-1.1.0")

    driver = relationship("Driver", back_populates="scores")


class RiskAssessment(TimestampMixin, Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (Index("ix_risk_driver_time", "driver_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    driver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    risk_level: Mapped[str] = mapped_column(String(16), default="low", index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    indicators: Mapped[list] = mapped_column(default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    recommendations: Mapped[list] = mapped_column(default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    model_version: Mapped[str] = mapped_column(String(40), default="risk-hgb-1.0.0")
    inputs: Mapped[dict] = mapped_column(default=dict)
    limitations: Mapped[list] = mapped_column(default=list)

    driver = relationship("Driver")
    vehicle = relationship("Vehicle")


class Incident(TimestampMixin, Base):
    __tablename__ = "incidents"
    __table_args__ = (Index("ix_incidents_org_status", "organisation_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"))
    driver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drivers.id", ondelete="SET NULL"), index=True)
    reporter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    incident_type: Mapped[str] = mapped_column(String(40), default="collision_suspected")
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="moderate", index=True)
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    evidence: Mapped[list] = mapped_column(default=list)
    investigation_notes: Mapped[Optional[str]] = mapped_column(Text)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)
    verified_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    emergency_contact_json: Mapped[dict] = mapped_column(default=dict)

    vehicle = relationship("Vehicle")
    driver = relationship("Driver", back_populates="incidents")
    reporter = relationship("User", foreign_keys=[reporter_id])  # type: ignore[name-defined]
    verified_by = relationship("User", foreign_keys=[verified_by_id])  # type: ignore[name-defined]
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])  # type: ignore[name-defined]


class MaintenanceRecord(TimestampMixin, Base):
    __tablename__ = "maintenance_records"
    __table_args__ = (Index("ix_maintenance_vehicle_time", "vehicle_id", "performed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    record_type: Mapped[str] = mapped_column(String(40), default="service")  # service|repair|inspection|tyre|other
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="completed")
    odometer_km: Mapped[float] = mapped_column(Float, default=0.0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    next_due_km: Mapped[Optional[float]] = mapped_column(Float)
    next_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    vendor: Mapped[Optional[str]] = mapped_column(String(120))
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    vehicle = relationship("Vehicle")


class MaintenanceAlert(TimestampMixin, Base):
    __tablename__ = "maintenance_alerts"
    __table_args__ = (Index("ix_maint_alerts_org_status", "organisation_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    alert_type: Mapped[str] = mapped_column(String(40))  # service_due|fault_code|insurance|low_health|predictive
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Float)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    vehicle = relationship("Vehicle")


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "is_read"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40), default="system", index=True)
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str] = mapped_column(String(20), default="in_app")  # in_app|email|sms
    delivery_status: Mapped[str] = mapped_column(String(20), default="delivered")
    related_type: Mapped[Optional[str]] = mapped_column(String(40))
    related_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    user = relationship("User")  # type: ignore[name-defined]


class RoadHazard(TimestampMixin, Base):
    __tablename__ = "road_hazards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    hazard_type: Mapped[str] = mapped_column(String(40))  # pothole|fog|flooding|construction|accident|animal|other
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    description: Mapped[Optional[str]] = mapped_column(String(255))
    reported_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)


class RoadHotspot(Base):
    """Historical accident hotspot reference points.

    IMPORTANT: rows are reference/illustrative data only. ``source_name`` records
    the provenance and ``is_illustrative`` marks rows that are not sourced from an
    official road-safety dataset. The UI labels these accordingly.
    """

    __tablename__ = "road_hotspots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organisation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(160))
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    radius_meters: Mapped[float] = mapped_column(Float, default=400.0)
    historical_count: Mapped[int] = mapped_column(Integer, default=0)
    source_name: Mapped[str] = mapped_column(String(200), default="Illustrative dataset")
    is_illustrative: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
