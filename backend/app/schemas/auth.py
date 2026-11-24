from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


def _clean(value: Optional[str]) -> Optional[str]:
    return value.strip() if isinstance(value, str) else value


class RegisterRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    organisation_name: str = Field(min_length=2, max_length=160)
    phone: Optional[str] = Field(default=None, max_length=24)
    accept_monitoring_policy: bool = False

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = _clean(value).lower()
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        if len(value) < 8 or value.lower() in {"password", "password123", "12345678"}:
            raise ValueError("Password must be at least 8 characters and not a common default")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: str
    job_title: Optional[str] = None
    organisation_id: Optional[int] = None
    is_active: bool
    is_verified: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    phone_masked: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class UserCreateRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    role: str = "driver"
    job_title: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _clean(value).lower()


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    job_title: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    phone: Optional[str] = None


class OrganisationOut(ORMModel):
    id: int
    name: str
    slug: str
    billing_email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: str
    monitoring_policy_accepted_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime


class OrganisationUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    billing_email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    monitoring_policy_accepted: Optional[bool] = None


class PlanOut(ORMModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    price_monthly: float
    currency: str
    max_vehicles: int
    max_drivers: int
    features: List[str]
    trial_days: int
    is_active: bool
    is_custom: bool
    sort_order: int


class SubscriptionOut(ORMModel):
    id: int
    organisation_id: int
    plan_id: int
    status: str
    seats: int
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool
    plan: Optional[PlanOut] = None


class PaymentOut(ORMModel):
    id: int
    invoice_number: str
    amount: float
    currency: str
    status: str
    provider: str
    description: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime


class UsageResponse(BaseModel):
    vehicles: int
    vehicle_limit: Optional[int]
    drivers: int
    driver_limit: Optional[int]
    events_this_month: int
    reports_this_month: int
    plan_code: str
    plan_name: str
    subscription_status: str
    trial_days_left: Optional[int]


class AuthMeResponse(BaseModel):
    user: UserOut
    organisation: Optional[OrganisationOut] = None
    subscription: Optional[SubscriptionOut] = None
    usage: Optional[UsageResponse] = None


class RegisterResponse(BaseModel):
    token: TokenResponse
    user: UserOut
    organisation: OrganisationOut


class LoginResponse(TokenResponse):
    user: UserOut
