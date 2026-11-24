from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ORMModel


# --------------------------------------------------------------------------
# Driving events
# --------------------------------------------------------------------------
class DrivingEventOut(ORMModel):
    id: int
    vehicle_id: int
    registration_number: Optional[str] = None
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    event_type: str
    severity: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_kph: Optional[float] = None
    speed_limit_kph: Optional[float] = None
    sensor_data: Dict[str, Any] = Field(default_factory=dict)
    recommended_action: Optional[str] = None
    is_simulated: bool
    source: str
    occurred_at: datetime


class EventCreate(BaseModel):
    vehicle_id: int
    driver_id: Optional[int] = None
    event_type: str
    severity: str = "medium"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_kph: Optional[float] = Field(default=None, ge=0, le=300)
    speed_limit_kph: Optional[float] = Field(default=None, ge=0, le=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    occurred_at: Optional[datetime] = None

    @field_validator("event_type")
    @classmethod
    def _type(cls, value: str) -> str:
        allowed = {
            "speeding", "harsh_braking", "rapid_acceleration", "aggressive_cornering",
            "excessive_duration", "seatbelt_violation", "possible_distraction",
            "collision_suspected", "geofence_breach", "route_deviation", "idle_excess",
        }
        if value not in allowed:
            raise ValueError(f"event_type must be one of {sorted(allowed)}")
        return value

    @field_validator("severity")
    @classmethod
    def _severity(cls, value: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        if value not in allowed:
            raise ValueError(f"severity must be one of {sorted(allowed)}")
        return value


class BehaviourSummary(BaseModel):
    period_days: int
    total_events: int
    high_risk_events: int
    critical_events: int
    events_per_100km: float
    distance_km: float
    by_type: List[Dict[str, Any]]
    by_severity: List[Dict[str, Any]]
    trend: List[Dict[str, Any]]
    top_drivers: List[Dict[str, Any]]
    safest_drivers: List[Dict[str, Any]]
    simulation_share_pct: float


class PatternInsight(BaseModel):
    key: str
    title: str
    description: str
    severity: str
    affected_drivers: int
    evidence: Dict[str, Any] = Field(default_factory=dict)
    recommended_action: str
    confidence: float


class PatternResponse(BaseModel):
    generated_at: datetime
    period_days: int
    patterns: List[PatternInsight]
    methodology: str
    limitations: List[str]


# --------------------------------------------------------------------------
# Scores
# --------------------------------------------------------------------------
class DriverScoreOut(ORMModel):
    id: int
    driver_id: int
    driver_name: Optional[str] = None
    period: str
    period_start: datetime
    period_end: datetime
    overall_score: float
    speed_score: float
    braking_score: float
    acceleration_score: float
    cornering_score: float
    seatbelt_score: Optional[float] = None
    consistency_score: float
    events_count: int
    distance_km: float
    confidence: float
    breakdown: Dict[str, Any] = Field(default_factory=dict)
    model_version: str
    created_at: datetime


class ScoreHistoryPoint(BaseModel):
    period_start: datetime
    overall_score: float
    period: str


class DriverScoreDetail(BaseModel):
    driver: Dict[str, Any]
    latest: Optional[DriverScoreOut] = None
    weekly: Optional[DriverScoreOut] = None
    monthly: Optional[DriverScoreOut] = None
    history: List[ScoreHistoryPoint]
    improvement_pct: Optional[float] = None
    recommendations: List[str]
    data_coverage: Dict[str, Any]
    disclaimer: str


class ScoreConfigIn(BaseModel):
    weights: Dict[str, float] = Field(default_factory=dict)
    min_distance_km: float = Field(default=5, ge=0, le=1000)


class ScoreConfigOut(BaseModel):
    weights: Dict[str, float]
    min_distance_km: float
    description: str


# --------------------------------------------------------------------------
# Risk
# --------------------------------------------------------------------------
class RiskAssessRequest(BaseModel):
    driver_id: int
    vehicle_id: Optional[int] = None


class RiskAssessmentOut(ORMModel):
    id: int
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    vehicle_id: Optional[int] = None
    registration_number: Optional[str] = None
    risk_level: str
    risk_score: float
    indicators: List[Dict[str, Any]]
    explanation: str
    recommendations: List[str]
    confidence: float
    model_version: str
    inputs: Dict[str, Any]
    limitations: List[str]
    created_at: datetime


class RiskOverview(BaseModel):
    generated_at: datetime
    total_assessed: int
    by_level: List[Dict[str, Any]]
    high_risk_drivers: List[Dict[str, Any]]
    fleet_risk_index: float
    model_info: Dict[str, Any]
    disclaimer: str


class RiskModelInfo(BaseModel):
    name: str
    version: str
    type: str
    metrics: Dict[str, Any]
    feature_importance: Dict[str, float] = Field(default_factory=dict)
    features: List[str]
    training: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str]
    disclaimer: str


# --------------------------------------------------------------------------
# Incidents
# --------------------------------------------------------------------------
class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    vehicle_id: Optional[int] = None
    driver_id: Optional[int] = None
    incident_type: str = "collision_suspected"
    severity: str = "moderate"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    occurred_at: Optional[datetime] = None
    evidence: Optional[List[Dict[str, Any]]] = None

    @field_validator("severity")
    @classmethod
    def _severity(cls, value: str) -> str:
        allowed = {"minor", "moderate", "severe", "critical"}
        if value not in allowed:
            raise ValueError(f"severity must be one of {sorted(allowed)}")
        return value

    @field_validator("incident_type")
    @classmethod
    def _type(cls, value: str) -> str:
        allowed = {
            "collision_suspected", "near_miss", "harsh_event", "breakdown",
            "theft", "geofence_breach", "other",
        }
        if value not in allowed:
            raise ValueError(f"incident_type must be one of {sorted(allowed)}")
        return value


class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    severity: Optional[str] = None
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = None
    investigation_notes: Optional[str] = None
    resolution_notes: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("status")
    @classmethod
    def _status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {"new", "under_investigation", "verified", "resolved", "false_alert"}
        if value not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return value


class IncidentOut(ORMModel):
    id: int
    vehicle_id: Optional[int] = None
    registration_number: Optional[str] = None
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    reporter_id: Optional[int] = None
    reporter_name: Optional[str] = None
    incident_type: str
    title: str
    description: Optional[str] = None
    severity: str
    status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    occurred_at: datetime
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    investigation_notes: Optional[str] = None
    resolution_notes: Optional[str] = None
    emergency_contact: Dict[str, Any] = Field(default_factory=dict)
    verified_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class IncidentSummary(BaseModel):
    total: int
    open: int
    under_investigation: int
    resolved: int
    false_alerts: int
    critical: int
    by_type: List[Dict[str, Any]]
    by_severity: List[Dict[str, Any]]
    response_time_hours_avg: Optional[float] = None


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
class NotificationOut(ORMModel):
    id: int
    type: str
    title: str
    message: str
    priority: str
    is_read: bool
    read_at: Optional[datetime] = None
    channel: str
    related_type: Optional[str] = None
    related_id: Optional[int] = None
    created_at: datetime


class NotificationPreferencesIn(BaseModel):
    in_app: bool = True
    email: bool = False
    sms: bool = False
    critical_only: bool = False
    quiet_hours_start: Optional[str] = Field(default=None, max_length=5)
    quiet_hours_end: Optional[str] = Field(default=None, max_length=5)


class NotificationPreferenceOut(NotificationPreferencesIn):
    model_config = ConfigDict(from_attributes=True)

    user_id: int


class RoadHazardIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    hazard_type: str
    severity: str = "medium"
    description: Optional[str] = Field(default=None, max_length=255)
    expires_in_hours: int = Field(default=24, ge=1, le=720)


class RoadHazardOut(ORMModel):
    id: int
    latitude: float
    longitude: float
    hazard_type: str
    severity: str
    description: Optional[str] = None
    status: str
    reported_by_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    is_simulated: bool
    created_at: datetime


class RouteAnalysisRequest(BaseModel):
    points: List[Dict[str, float]] = Field(min_length=2, max_length=200)


class RouteAnalysisResponse(BaseModel):
    distance_km: float
    risk_rating: str
    risk_score: float
    hazard_count: int
    hotspot_count: int
    warnings: List[str]
    recommendations: List[str]
    data_sources: List[str]
    disclaimer: str
