"""Enumerations shared by models and schemas."""

from enum import Enum


class VehicleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNDER_MAINTENANCE = "under_maintenance"
    OFFLINE = "offline"


class DriverStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"


class EventSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(str, Enum):
    SPEEDING = "speeding"
    HARSH_BRAKING = "harsh_braking"
    RAPID_ACCELERATION = "rapid_acceleration"
    AGGRESSIVE_CORNERING = "aggressive_cornering"
    EXCESSIVE_DURATION = "excessive_duration"
    SEATBELT_VIOLATION = "seatbelt_violation"
    POSSIBLE_DISTRACTION = "possible_distraction"
    COLLISION_SUSPECTED = "collision_suspected"
    GEOFENCE_BREACH = "geofence_breach"
    ROUTE_DEVIATION = "route_deviation"
    IDLE_EXCESS = "idle_excess"


EVENT_TYPE_LABELS = {
    EventType.SPEEDING.value: "Speeding",
    EventType.HARSH_BRAKING.value: "Harsh braking",
    EventType.RAPID_ACCELERATION.value: "Rapid acceleration",
    EventType.AGGRESSIVE_CORNERING.value: "Aggressive cornering",
    EventType.EXCESSIVE_DURATION.value: "Excessive driving duration",
    EventType.SEATBELT_VIOLATION.value: "Seatbelt non-compliance",
    EventType.POSSIBLE_DISTRACTION.value: "Possible distraction",
    EventType.COLLISION_SUSPECTED.value: "Possible collision",
    EventType.GEOFENCE_BREACH.value: "Geofence breach",
    EventType.ROUTE_DEVIATION.value: "Route deviation",
    EventType.IDLE_EXCESS.value: "Excessive idling",
}


class IncidentStatus(str, Enum):
    NEW = "new"
    UNDER_INVESTIGATION = "under_investigation"
    VERIFIED = "verified"
    RESOLVED = "resolved"
    FALSE_ALERT = "false_alert"


class IncidentSeverity(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(str, Enum):
    SPEEDING = "speeding_alert"
    HARSH_BRAKING = "harsh_braking_alert"
    VEHICLE_OFFLINE = "vehicle_offline"
    MAINTENANCE = "maintenance_reminder"
    LICENCE_EXPIRY = "licence_expiry"
    POSSIBLE_ACCIDENT = "possible_accident"
    ROUTE_DEVIATION = "route_deviation"
    DRIVER_WARNING = "driver_safety_warning"
    INCIDENT_UPDATE = "incident_update"
    SYSTEM = "system"
    COACHING = "coaching"


class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class MaintenanceStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class SubscriptionStatus(str, Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class ReportFormat(str, Enum):
    PDF = "pdf"
    CSV = "csv"


class ReportStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class TelemetrySource(str, Enum):
    DEVICE = "device"
    SIMULATED = "simulated"
    MANUAL = "manual"


class HazardStatus(str, Enum):
    ACTIVE = "active"
    CLEARED = "cleared"
    EXPIRED = "expired"


class AIModelStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
