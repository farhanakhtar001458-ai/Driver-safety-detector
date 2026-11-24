"""Audit log endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.deps import Pagination, get_db, org_filter, require_permission
from app.models import AuditLog, User
from app.schemas.common import Paginated
from app.schemas.saas import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get("", response_model=Paginated[AuditLogOut])
def list_audit_logs(
    pagination: Pagination = Depends(),
    action: Optional[str] = Query(default=None),
    resource_type: Optional[str] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    from_time: Optional[datetime] = Query(default=None, alias="from"),
    to_time: Optional[datetime] = Query(default=None, alias="to"),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(AuditLog).options(joinedload(AuditLog.user)), AuditLog, user, organisation_id)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if from_time:
        query = query.filter(AuditLog.created_at >= from_time)
    if to_time:
        query = query.filter(AuditLog.created_at <= to_time)
    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    items = []
    for row in rows:
        item = AuditLogOut.model_validate(row)
        item.user_name = row.user.full_name if row.user else None
        items.append(item)
    return Paginated[AuditLogOut].create(items, total, pagination.page, pagination.page_size)
