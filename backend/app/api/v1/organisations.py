"""Organisation, team and platform administration endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.deps import Pagination, get_db, get_organisation, require_permission, require_roles
from app.core.rbac import ROLE_LABELS, UserRole, can_assign_role
from app.core.security import encrypt_value, hash_password
from app.models import (
    AuditLog,
    Driver,
    NotificationPreference,
    Organisation,
    Subscription,
    SubscriptionPlan,
    User,
    Vehicle,
)
from app.schemas.auth import (
    OrganisationOut,
    OrganisationUpdateRequest,
    PlanOut,
    SubscriptionOut,
    UsageResponse,
    UserCreateRequest,
    UserOut,
    UserUpdateRequest,
)
from app.schemas.common import MessageResponse, Paginated
from app.services import billing
from app.services.audit import log_action
from app.services.serializers import user_out

router = APIRouter(prefix="/organisations", tags=["Organisations"])


@router.get("/me", response_model=OrganisationOut)
def get_my_organisation(organisation: Organisation = Depends(get_organisation)):
    return OrganisationOut.model_validate(organisation)


@router.patch("/me", response_model=OrganisationOut)
def update_my_organisation(
    payload: OrganisationUpdateRequest,
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    user: User = Depends(require_permission("settings:manage")),
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    policy = data.pop("monitoring_policy_accepted", None)
    if policy is True and not organisation.monitoring_policy_accepted_at:
        organisation.monitoring_policy_accepted_at = datetime.utcnow()
    for key, value in data.items():
        if value is not None:
            setattr(organisation, key, value)
    db.flush()
    log_action(
        db,
        user=user,
        action="organisation.update",
        resource_type="organisation",
        resource_id=organisation.id,
        detail={"fields": list(data.keys())},
        request=request,
    )
    return OrganisationOut.model_validate(organisation)


@router.get("/me/usage", response_model=UsageResponse)
def get_usage(
    organisation: Organisation = Depends(get_organisation),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("billing:read")),
):
    return UsageResponse(**billing.usage(db, organisation))


# --------------------------------------------------------------------------
# Platform administration (super admin)
# --------------------------------------------------------------------------
@router.get("", response_model=Paginated[OrganisationOut])
def list_organisations(
    pagination: Pagination = Depends(),
    search: Optional[str] = Query(default=None),
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    query = db.query(Organisation)
    if search:
        query = query.filter(Organisation.name.ilike(f"%{search}%"))
    total = query.count()
    items = query.order_by(Organisation.created_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[OrganisationOut].create(
        [OrganisationOut.model_validate(item) for item in items], total, pagination.page, pagination.page_size
    )


@router.post("", response_model=OrganisationOut, status_code=201)
def create_organisation(
    payload: dict,
    request: Request,
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    name = (payload.get("name") or "").strip()
    admin_email = (payload.get("admin_email") or "").strip().lower()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="name is required")
    if not admin_email or "@" not in admin_email:
        raise HTTPException(status_code=422, detail="A valid admin_email is required")
    if db.query(Organisation).filter(Organisation.name == name).first():
        raise HTTPException(status_code=409, detail="An organisation with this name already exists")

    slug = name.lower().replace(" ", "-")[:80]
    organisation = Organisation(name=name, slug=slug, settings_json={"created_by": "platform_admin"})
    db.add(organisation)
    db.flush()

    admin = User(
        organisation_id=organisation.id,
        email=admin_email,
        password_hash=hash_password(payload.get("admin_password") or "ChangeMe@12345"),
        full_name=payload.get("admin_name") or "Organisation Admin",
        role=UserRole.ORG_ADMIN.value,
        is_active=True,
        is_verified=True,
    )
    db.add(admin)
    db.flush()
    db.add(NotificationPreference(user_id=admin.id, in_app=True, email=True))
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == (payload.get("plan") or "starter")).first()
    if plan:
        now = datetime.utcnow()
        db.add(
            Subscription(
                organisation_id=organisation.id,
                plan_id=plan.id,
                status="trialing",
                seats=1,
                trial_start=now,
                trial_end=now + timedelta(days=plan.trial_days or 14),
                current_period_start=now,
                current_period_end=now + timedelta(days=plan.trial_days or 14),
            )
        )
    db.flush()
    log_action(
        db,
        user=user,
        action="organisation.create",
        resource_type="organisation",
        resource_id=organisation.id,
        detail={"name": name, "admin_email": admin_email},
        request=request,
    )
    return OrganisationOut.model_validate(organisation)


@router.get("/{organisation_id}", response_model=OrganisationOut)
def get_organisation_by_id(
    organisation_id: int,
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    organisation = db.get(Organisation, organisation_id)
    if not organisation:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return OrganisationOut.model_validate(organisation)


@router.get("/{organisation_id}/usage", response_model=UsageResponse)
def get_organisation_usage(
    organisation_id: int,
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    organisation = db.get(Organisation, organisation_id)
    if not organisation:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return UsageResponse(**billing.usage(db, organisation))


@router.get("/{organisation_id}/subscription", response_model=SubscriptionOut)
def get_organisation_subscription(
    organisation_id: int,
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    organisation = db.get(Organisation, organisation_id)
    if not organisation:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return SubscriptionOut.model_validate(billing.get_or_create_subscription(db, organisation))


@router.get("/{organisation_id}/plans", response_model=list[PlanOut])
def list_plans(
    organisation_id: int,
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.sort_order).all()
    return [PlanOut.model_validate(plan) for plan in plans]


# --------------------------------------------------------------------------
# Team management
# --------------------------------------------------------------------------
@router.get("/me/team", response_model=Paginated[UserOut])
def list_team(
    pagination: Pagination = Depends(),
    role: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    organisation: Organisation = Depends(get_organisation),
    _user: User = Depends(require_permission("team:read")),
    db: Session = Depends(get_db),
):
    query = db.query(User).filter(User.organisation_id == organisation.id)
    if role:
        query = query.filter(User.role == role)
    if search:
        query = query.filter(User.full_name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%"))
    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[UserOut].create([user_out(u) for u in users], total, pagination.page, pagination.page_size)


@router.post("/me/team", response_model=UserOut, status_code=201)
def create_team_member(
    payload: UserCreateRequest,
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    actor: User = Depends(require_permission("team:manage")),
    db: Session = Depends(get_db),
):
    try:
        target_role = UserRole(payload.role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"role must be one of {[r.value for r in UserRole]}")
    if target_role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super administrators are created outside organisations")
    if not can_assign_role(actor.role, target_role):
        raise HTTPException(status_code=403, detail="You cannot assign this role")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    user = User(
        organisation_id=organisation.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=target_role.value,
        job_title=payload.job_title,
        phone_encrypted=encrypt_value(payload.phone) if payload.phone else None,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(NotificationPreference(user_id=user.id, in_app=True, email=False, sms=False))
    log_action(
        db,
        user=actor,
        action="team.member.create",
        resource_type="user",
        resource_id=user.id,
        detail={"role": target_role.value, "email": payload.email},
        request=request,
    )
    return user_out(user)


@router.patch("/me/team/{user_id}", response_model=UserOut)
def update_team_member(
    user_id: int,
    payload: UserUpdateRequest,
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    actor: User = Depends(require_permission("team:manage")),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.organisation_id == organisation.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Team member not found")

    if payload.role and payload.role != user.role:
        try:
            target_role = UserRole(payload.role)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid role")
        if not can_assign_role(actor.role, target_role):
            raise HTTPException(status_code=403, detail="You cannot assign this role")
        user.role = target_role.value

    if payload.full_name:
        user.full_name = payload.full_name
    if payload.job_title is not None:
        user.job_title = payload.job_title
    if payload.phone is not None:
        user.phone_encrypted = encrypt_value(payload.phone)
    if payload.is_active is not None and user.id != actor.id:
        user.is_active = payload.is_active
    db.flush()
    log_action(
        db,
        user=actor,
        action="team.member.update",
        resource_type="user",
        resource_id=user.id,
        detail={"fields": list(payload.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    return user_out(user)


@router.delete("/me/team/{user_id}", response_model=MessageResponse)
def deactivate_team_member(
    user_id: int,
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    actor: User = Depends(require_permission("team:manage")),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.organisation_id == organisation.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Team member not found")
    if user.id == actor.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    user.is_active = False
    db.flush()
    log_action(
        db,
        user=actor,
        action="team.member.deactivate",
        resource_type="user",
        resource_id=user.id,
        request=request,
    )
    return MessageResponse(message="Team member deactivated")
