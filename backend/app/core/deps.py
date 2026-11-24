"""Shared FastAPI dependencies: current user, org scoping, permission checks."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.rbac import UserRole, role_has_permission
from app.core.security import decode_token
from app.db.session import get_db
from app.models import GPSDevice, Organisation, Subscription, User

bearer_scheme = HTTPBearer(auto_error=False)


def _credentials(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    token_query: Optional[str] = Query(default=None, alias="token"),
) -> Optional[str]:
    if credentials and credentials.credentials:
        return credentials.credentials
    return token_query


def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(_credentials),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token, expected_type="access")
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or not found")
    return user


def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    return user


class PermissionChecker:
    """Dependency factory: ``Depends(require_permission("vehicles:create"))``."""

    def __init__(self, permission: str):
        self.permission = permission

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if not role_has_permission(user.role, self.permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission '{self.permission}' for role '{user.role}'",
            )
        return user


def require_permission(permission: str) -> PermissionChecker:
    return PermissionChecker(permission)


def require_roles(*roles: str):
    allowed = {r if isinstance(r, str) else r.value for r in roles}

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Role not permitted for this operation")
        return user

    return _checker


def get_organisation(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Organisation:
    """Return the caller's organisation. Super admins must pass an explicit org id."""
    if user.role == UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=400,
            detail="Super administrators operate across organisations. Use organisation-specific endpoints.",
        )
    if not user.organisation_id:
        raise HTTPException(status_code=403, detail="User is not linked to an organisation")
    organisation = db.get(Organisation, user.organisation_id)
    if not organisation:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return organisation


def resolve_org_id(
    db: Session,
    user: User,
    requested_org_id: Optional[int] = None,
) -> Optional[int]:
    """Resolve the tenant filter for a request.

    Non-super users are always pinned to their own organisation (requested values
    are ignored), which is the core tenant-isolation guarantee.
    """
    if user.role == UserRole.SUPER_ADMIN.value:
        return requested_org_id
    return user.organisation_id


def scope_organisation(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organisation:
    """Organisation context that also supports super admin via ?organisation_id=."""
    if user.role == UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=400, detail="Super admins must specify an organisation_id")
    return get_organisation(user, db)


def get_optional_org_id(
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(get_current_user),
) -> Optional[int]:
    return resolve_org_id(None, user, organisation_id)


def get_device(
    db: Session = Depends(get_db),
    x_device_key: Optional[str] = Header(default=None, alias="X-Device-Key"),
) -> GPSDevice:
    if not x_device_key:
        raise HTTPException(status_code=401, detail="Missing X-Device-Key header")
    from app.core.security import verify_device_key

    candidates = db.query(GPSDevice).filter(GPSDevice.key_hash.isnot(None)).all()
    if not candidates:
        raise HTTPException(status_code=401, detail="Device authentication failed")
    # Constant-time verification against each configured device.
    for candidate in candidates:
        if candidate.key_hash and verify_device_key(x_device_key, candidate.key_hash):
            return candidate
    raise HTTPException(status_code=401, detail="Device authentication failed")


def get_subscription(db: Session, organisation_id: int) -> Optional[Subscription]:
    return db.query(Subscription).filter(Subscription.organisation_id == organisation_id).first()


class Pagination:
    def __init__(
        self,
        page: int = Query(1, ge=1, le=1000),
        page_size: int = Query(20, ge=1, le=200),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def org_filter(query, model, user: User, requested_org_id: Optional[int] = None):
    """Apply tenant scoping to a SELECT query.

    Non-super users are hard-pinned to their organisation. Super admins may pass
    an explicit organisation filter, otherwise they see every tenant.
    """
    if user.role == UserRole.SUPER_ADMIN.value:
        if requested_org_id:
            return query.filter(model.organisation_id == requested_org_id)
        return query
    return query.filter(model.organisation_id == user.organisation_id)


def ensure_org_access(obj_organisation_id: Optional[int], user: User) -> None:
    if user.role == UserRole.SUPER_ADMIN.value:
        return
    if obj_organisation_id != user.organisation_id:
        raise HTTPException(status_code=404, detail="Resource not found")
