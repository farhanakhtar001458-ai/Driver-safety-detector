"""Subscription plans, billing and SaaS administration."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, get_db, get_organisation, require_permission
from app.models import Organisation, Payment, Subscription, SubscriptionPlan, User
from app.schemas.auth import PaymentOut, PlanOut, SubscriptionOut, UsageResponse
from app.schemas.common import MessageResponse
from app.schemas.saas import PlanUpgradeRequest
from app.services import billing
from app.services.audit import log_action

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


def _subscription_out(subscription: Subscription) -> SubscriptionOut:
    return SubscriptionOut.model_validate(subscription)


@router.get("/plans", response_model=list[PlanOut])
def list_plans(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plans = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.sort_order)
        .all()
    )
    return [PlanOut.model_validate(plan) for plan in plans]


@router.get("/me", response_model=SubscriptionOut)
def my_subscription(
    organisation: Organisation = Depends(get_organisation),
    _user: User = Depends(require_permission("billing:read")),
    db: Session = Depends(get_db),
):
    return _subscription_out(billing.get_or_create_subscription(db, organisation))


@router.get("/me/usage", response_model=UsageResponse)
def my_usage(
    organisation: Organisation = Depends(get_organisation),
    _user: User = Depends(require_permission("billing:read")),
    db: Session = Depends(get_db),
):
    return UsageResponse(**billing.usage(db, organisation))


@router.post("/upgrade", response_model=dict)
def upgrade_plan(
    payload: PlanUpgradeRequest,
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    user: User = Depends(require_permission("billing:manage")),
    db: Session = Depends(get_db),
):
    subscription, payment = billing.upgrade(db, organisation, payload.plan_code, payload.seats, actor=user)
    log_action(
        db,
        user=user,
        action="subscription.upgrade",
        resource_type="subscription",
        resource_id=subscription.id,
        detail={"plan": payload.plan_code, "seats": payload.seats, "invoice": payment.invoice_number},
        request=request,
    )
    return {
        "message": (
            "Plan updated. No payment provider is configured, so the invoice remains pending "
            "until billing is enabled."
            if payment.status == "pending"
            else "Plan updated."
        ),
        "subscription": _subscription_out(subscription).model_dump(),
        "payment": PaymentOut.model_validate(payment).model_dump(),
    }


@router.post("/cancel", response_model=SubscriptionOut)
def cancel_subscription(
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    user: User = Depends(require_permission("billing:manage")),
    db: Session = Depends(get_db),
):
    subscription = billing.cancel(db, organisation)
    log_action(
        db,
        user=user,
        action="subscription.cancel",
        resource_type="subscription",
        resource_id=subscription.id,
        request=request,
    )
    return _subscription_out(subscription)


@router.get("/payments", response_model=list[PaymentOut])
def payments(
    organisation: Organisation = Depends(get_organisation),
    _user: User = Depends(require_permission("billing:read")),
    db: Session = Depends(get_db),
):
    return [PaymentOut.model_validate(payment) for payment in billing.billing_history(db, organisation)]


@router.get("/compare", response_model=list[PlanOut])
def compare_plans(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plans = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.sort_order)
        .all()
    )
    return [PlanOut.model_validate(plan) for plan in plans]
