"""Audit trail helper.

Mutating requests are recorded with actor, action, resource, payload summary and
network origin. Read access is not logged by default (volume), but sensitive
reads such as audit-log export could be added here.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog


def client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def log_action(
    db: Session,
    *,
    user=None,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[Any] = None,
    detail: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
    organisation_id: Optional[int] = None,
) -> AuditLog:
    entry = AuditLog(
        organisation_id=organisation_id or (user.organisation_id if user else None),
        user_id=user.id if user else None,
        action=action[:120],
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        detail={
            **(detail or {}),
            **({"email": user.email} if user and not detail else {}),
        },
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:255] if request else None,
    )
    db.add(entry)
    db.flush()
    return entry
