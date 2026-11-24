"""Authentication endpoints: register, login, refresh, logout, password change."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.rbac import UserRole, can_assign_role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    encrypt_value,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import (
    AuditLog,
    Driver,
    NotificationPreference,
    Organisation,
    RefreshToken,
    Role,
    Subscription,
    SubscriptionPlan,
    User,
    UserSession,
)
from app.schemas.auth import (
    AuthMeResponse,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    OrganisationOut,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    SubscriptionOut,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.services import billing
from app.services.audit import client_ip, log_action
from app.services.serializers import user_out

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _issue_tokens(
    db: Session, user: User, request: Optional[Request] = None
) -> tuple[str, str, str, datetime]:
    claims = {"role": user.role, "org_id": user.organisation_id}
    access = create_access_token(str(user.id), claims)
    refresh, jti, expires_at = create_refresh_token(str(user.id), claims)
    ip = client_ip(request)
    agent = request.headers.get("user-agent", "")[:255] if request else None
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=expires_at,
            user_agent=agent,
            ip_address=ip,
        )
    )
    db.add(UserSession(user_id=user.id, refresh_jti=jti, ip_address=ip, user_agent=agent))
    db.flush()
    return access, refresh, jti, expires_at


def _token_response(db: Session, user: User, request: Optional[Request]) -> TokenResponse:
    access, refresh, _jti, expires_at = _issue_tokens(db, user, request)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _slugify(name: str) -> str:
    slug = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:80] or "organisation"


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    base_slug = _slugify(payload.organisation_name)
    slug = base_slug
    suffix = 1
    while db.query(Organisation).filter(Organisation.slug == slug).first():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    organisation = Organisation(
        name=payload.organisation_name.strip(),
        slug=slug,
        monitoring_policy_accepted_at=datetime.utcnow() if payload.accept_monitoring_policy else None,
        settings_json={"onboarding": "self_service"},
    )
    db.add(organisation)
    db.flush()

    role_row = db.query(Role).filter(Role.code == UserRole.ORG_ADMIN.value).first()
    user = User(
        organisation_id=organisation.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=UserRole.ORG_ADMIN.value,
        job_title="Administrator",
        phone_encrypted=encrypt_value(payload.phone)
        if payload.phone
        else None,
        is_active=True,
        is_verified=True,
    )
    if role_row:
        user.role = role_row.code
    db.add(user)
    db.flush()
    db.add(NotificationPreference(user_id=user.id, in_app=True, email=True, sms=False))

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "professional").first()
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

    access, refresh, _jti, _exp = _issue_tokens(db, user, request)
    log_action(
        db,
        user=user,
        action="auth.register",
        resource_type="organisation",
        resource_id=organisation.id,
        detail={"organisation": organisation.name, "plan": plan.code if plan else "trial"},
        request=request,
    )
    return RegisterResponse(
        token=TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
        user=user_out(user),
        organisation=OrganisationOut.model_validate(organisation),
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    user.last_login_at = datetime.utcnow()
    db.flush()
    access, refresh, _jti, _exp = _issue_tokens(db, user, request)
    log_action(db, user=user, action="auth.login", resource_type="session", request=request)
    return LoginResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_out(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    token_data = decode_token(payload.refresh_token, expected_type="refresh")
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    jti = token_data.get("jti")
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(payload.refresh_token)).first()
    if not stored or stored.revoked_at is not None or stored.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token is no longer valid")

    try:
        user_id = int(token_data["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token subject")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive")

    # Rotate: invalidate the presented token and its session, then issue a new
    # pair. _issue_tokens records a fresh UserSession for the new jti.
    stored.revoked_at = datetime.utcnow()
    db.query(UserSession).filter(UserSession.refresh_jti == jti).update(
        {"revoked_at": datetime.utcnow()}, synchronize_session=False
    )
    access, new_refresh, new_jti, _exp = _issue_tokens(db, user, request)
    db.flush()
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, request: Request, db: Session = Depends(get_db)):
    token_data = decode_token(payload.refresh_token, expected_type="refresh")
    jti = token_data.get("jti") if token_data else None
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(payload.refresh_token)).first()
    if stored and stored.revoked_at is None:
        stored.revoked_at = datetime.utcnow()
        if jti:
            db.query(UserSession).filter(UserSession.refresh_jti == jti).update(
                {"revoked_at": datetime.utcnow()}, synchronize_session=False
            )
        db.flush()
    return MessageResponse(message="Signed out")


@router.get("/me", response_model=AuthMeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    organisation = None
    subscription = None
    usage = None
    if user.organisation_id:
        organisation = db.get(Organisation, user.organisation_id)
        if organisation:
            subscription = billing.get_or_create_subscription(db, organisation)
            usage = billing.usage(db, organisation)
    return AuthMeResponse(
        user=user_out(user),
        organisation=OrganisationOut.model_validate(organisation) if organisation else None,
        subscription=SubscriptionOut.model_validate(subscription) if subscription else None,
        usage=usage,
    )


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="New password must differ from the current password")
    user.password_hash = hash_password(payload.new_password)
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id).update({"revoked_at": datetime.utcnow()})
    db.flush()
    log_action(db, user=user, action="auth.change_password", resource_type="user", resource_id=user.id, request=request)
    return MessageResponse(message="Password updated. Please sign in again on other devices.")
