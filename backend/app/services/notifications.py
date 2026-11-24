"""Notification creation and delivery (in-app, email outbox, SMS stub)."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Notification, NotificationPreference, User

# Recipients by role for each notification type. Purpose: avoid alerting
# drivers about fleet-wide operational noise, and avoid alerting managers to
# routine coaching chatter.
RECIPIENT_ROLES: dict[str, tuple[str, ...]] = {
    "speeding_alert": ("org_admin", "fleet_manager", "safety_officer"),
    "harsh_braking_alert": ("org_admin", "fleet_manager", "safety_officer"),
    "vehicle_offline": ("org_admin", "fleet_manager"),
    "maintenance_reminder": ("org_admin", "fleet_manager"),
    "licence_expiry": ("org_admin", "fleet_manager", "driver"),
    "possible_accident": ("org_admin", "fleet_manager", "safety_officer"),
    "route_deviation": ("org_admin", "fleet_manager"),
    "driver_safety_warning": ("org_admin", "fleet_manager", "safety_officer"),
    "incident_update": ("org_admin", "fleet_manager", "safety_officer"),
    "system": ("org_admin",),
    "coaching": ("driver",),
}


def _recipients(db: Session, organisation_id: int, notification_type: str) -> list[User]:
    roles = RECIPIENT_ROLES.get(notification_type, ("org_admin", "fleet_manager"))
    users = (
        db.query(User)
        .filter(User.organisation_id == organisation_id, User.is_active.is_(True))
        .all()
    )
    return [user for user in users if user.role in roles]


def create_notification(
    db: Session,
    *,
    organisation_id: int,
    notification_type: str,
    title: str,
    message: str,
    priority: str = "medium",
    user_ids: Optional[Iterable[int]] = None,
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
    channel: str = "in_app",
    respect_preferences: bool = True,
) -> list[Notification]:
    if user_ids is None:
        recipients = _recipients(db, organisation_id, notification_type)
        user_ids = [user.id for user in recipients]

    notifications: list[Notification] = []
    for user_id in user_ids:
        if respect_preferences:
            prefs = (
                db.query(NotificationPreference)
                .filter(NotificationPreference.user_id == user_id)
                .first()
            )
            if prefs and not prefs.in_app:
                continue
            if prefs and prefs.critical_only and priority not in {"high", "urgent"}:
                continue
        notification = Notification(
            organisation_id=organisation_id,
            user_id=user_id,
            type=notification_type,
            title=title[:160],
            message=message,
            priority=priority,
            channel=channel,
            related_type=related_type,
            related_id=related_id,
            delivery_status="delivered" if channel == "in_app" else "queued",
        )
        db.add(notification)
        notifications.append(notification)
    db.flush()
    return notifications


def create_for_users(
    db: Session,
    users: Iterable[User],
    *,
    organisation_id: int,
    notification_type: str,
    title: str,
    message: str,
    priority: str = "medium",
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
) -> list[Notification]:
    return create_notification(
        db,
        organisation_id=organisation_id,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        user_ids=[user.id for user in users],
        related_type=related_type,
        related_id=related_id,
    )


def dispatch_email(db: Session, notification: Notification) -> str:
    """Send email if SMTP is configured; otherwise leave as an honest outbox entry.

    The platform never reports an email as sent when the transport is not
    configured. ``delivery_status`` reflects reality.
    """
    if not settings.SMTP_HOST:
        notification.delivery_status = "not_configured"
        notification.channel = "email"
        db.flush()
        return "not_configured"
    # Real SMTP implementation is intentionally small and synchronous; in
    # production move to a background worker queue.
    import smtplib
    from email.mime.text import MIMEText

    user = db.get(User, notification.user_id) if notification.user_id else None
    if not user or not user.email:
        notification.delivery_status = "failed"
        db.flush()
        return "failed"
    try:
        msg = MIMEText(notification.message)
        msg["Subject"] = notification.title
        msg["From"] = settings.SMTP_FROM
        msg["To"] = user.email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [user.email], msg.as_string())
        notification.delivery_status = "sent"
    except Exception:
        notification.delivery_status = "failed"
    db.flush()
    return notification.delivery_status


def dispatch_sms(db: Session, notification: Notification) -> str:
    """SMS requires a provider contract. Without configuration this is explicit."""
    if settings.SMS_PROVIDER in {"", "none"} or not settings.SMS_API_KEY:
        notification.delivery_status = "not_configured"
        notification.channel = "sms"
        db.flush()
        return "not_configured"
    # Provider integration point: implement the selected gateway here.
    notification.delivery_status = "queued"
    db.flush()
    return "queued"


def mark_read(db: Session, notification: Notification) -> Notification:
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.flush()
    return notification
