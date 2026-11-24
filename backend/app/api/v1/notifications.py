"""Notification centre and delivery preferences."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import Pagination, get_current_user, get_db, org_filter, require_permission
from app.models import Notification, NotificationPreference, User
from app.schemas.common import MessageResponse, Paginated
from app.schemas.safety import NotificationOut, NotificationPreferenceOut, NotificationPreferencesIn
from app.services.notifications import dispatch_email, dispatch_sms, mark_read

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=Paginated[NotificationOut])
def list_notifications(
    pagination: Pagination = Depends(),
    unread: Optional[bool] = Query(default=None),
    notification_type: Optional[str] = Query(default=None, alias="type"),
    priority: Optional[str] = Query(default=None),
    user: User = Depends(require_permission("notifications:read")),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(Notification.user_id == user.id)
    if unread is not None:
        # unread=true -> only unread; unread=false -> only read
        query = query.filter(Notification.is_read.is_(not unread))
    if notification_type:
        query = query.filter(Notification.type == notification_type)
    if priority:
        query = query.filter(Notification.priority == priority)
    total = query.count()
    rows = query.order_by(Notification.created_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[NotificationOut].create(
        [NotificationOut.model_validate(row) for row in rows], total, pagination.page, pagination.page_size
    )


@router.get("/unread-count")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user.id, Notification.is_read.is_(False))
        .scalar()
        or 0
    )
    return {"unread": count}


@router.get("/stats")
def notification_stats(user: User = Depends(require_permission("notifications:read")), db: Session = Depends(get_db)):
    rows = (
        db.query(Notification.type, Notification.priority, Notification.is_read, func.count(Notification.id))
        .filter(Notification.user_id == user.id)
        .group_by(Notification.type, Notification.priority, Notification.is_read)
        .all()
    )
    by_type: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for notification_type, priority, is_read, count in rows:
        by_type[notification_type] = by_type.get(notification_type, 0) + count
        by_priority[priority] = by_priority.get(priority, 0) + count
    return {
        "total": sum(by_type.values()),
        "by_type": [{"type": key, "count": value} for key, value in sorted(by_type.items(), key=lambda kv: -kv[1])],
        "by_priority": [{"priority": key, "count": value} for key, value in by_priority.items()],
    }


@router.post("/read-all", response_model=MessageResponse)
def read_all(user: User = Depends(require_permission("notifications:manage")), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read.is_(False)).all()
    for row in rows:
        mark_read(db, row)
    db.flush()
    return MessageResponse(message=f"Marked {len(rows)} notification(s) as read")


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: int,
    user: User = Depends(require_permission("notifications:read")),
    db: Session = Depends(get_db),
):
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    mark_read(db, notification)
    return NotificationOut.model_validate(notification)


@router.post("/{notification_id}/dispatch", response_model=dict)
def dispatch_notification(
    notification_id: int,
    channel: str = Query(default="email"),
    user: User = Depends(require_permission("notifications:manage")),
    db: Session = Depends(get_db),
):
    """Attempt delivery through a configured channel.

    If SMTP / SMS is not configured the API reports ``not_configured`` instead of
    pretending the message was sent.
    """
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    status = dispatch_email(db, notification) if channel == "email" else dispatch_sms(db, notification)
    return {
        "notification_id": notification.id,
        "channel": channel,
        "delivery_status": status,
        "message": {
            "sent": "Message handed to the email transport.",
            "queued": "Message queued for the SMS provider.",
            "not_configured": "This delivery channel is not configured on the server.",
            "failed": "Delivery failed. Check server logs.",
        }.get(status, status),
    }


@router.get("/preferences", response_model=NotificationPreferenceOut)
def get_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.user_id == user.id)
        .first()
    )
    if not prefs:
        prefs = NotificationPreference(user_id=user.id, in_app=True, email=False, sms=False)
        db.add(prefs)
        db.flush()
    return NotificationPreferenceOut.model_validate(prefs)


@router.put("/preferences", response_model=NotificationPreferenceOut)
def update_preferences(
    payload: NotificationPreferencesIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.user_id == user.id)
        .first()
    )
    if not prefs:
        prefs = NotificationPreference(user_id=user.id)
        db.add(prefs)
    for key, value in payload.model_dump().items():
        setattr(prefs, key, value)
    db.flush()
    return NotificationPreferenceOut.model_validate(prefs)
