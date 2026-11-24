"""Subscription plans, quota enforcement and billing history.

There is no payment provider integrated by default. Upgrades create a
``pending`` invoice so the commercial flow can be demonstrated without
pretending a card was charged. Configure a PSP before enabling live billing.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, QuotaExceededError
from app.models import (
    Driver,
    DrivingEvent,
    MaintenanceAlert,
    Organisation,
    Payment,
    Report,
    Subscription,
    SubscriptionPlan,
    Vehicle,
)

TRIAL_DAYS = 14


def get_plan(db: Session, code: str) -> SubscriptionPlan:
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == code).first()
    if not plan:
        raise NotFoundError(f"Plan '{code}' does not exist")
    return plan


def get_or_create_subscription(db: Session, organisation: Organisation) -> Subscription:
    subscription = (
        db.query(Subscription).filter(Subscription.organisation_id == organisation.id).first()
    )
    if subscription:
        return subscription
    plan = get_plan(db, "professional")
    now = datetime.utcnow()
    subscription = Subscription(
        organisation_id=organisation.id,
        plan_id=plan.id,
        status="trialing",
        seats=1,
        trial_start=now,
        trial_end=now + timedelta(days=plan.trial_days or TRIAL_DAYS),
        current_period_start=now,
        current_period_end=now + timedelta(days=plan.trial_days or TRIAL_DAYS),
    )
    db.add(subscription)
    db.flush()
    return subscription


def usage(db: Session, organisation: Organisation) -> dict:
    subscription = get_or_create_subscription(db, organisation)
    plan = subscription.plan
    vehicles = (
        db.query(func.count(Vehicle.id))
        .filter(Vehicle.organisation_id == organisation.id, Vehicle.is_archived.is_(False))
        .scalar()
        or 0
    )
    drivers = (
        db.query(func.count(Driver.id)).filter(Driver.organisation_id == organisation.id).scalar() or 0
    )
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    events = (
        db.query(func.count(DrivingEvent.id))
        .filter(
            DrivingEvent.organisation_id == organisation.id,
            DrivingEvent.occurred_at >= month_start,
        )
        .scalar()
        or 0
    )
    reports = (
        db.query(func.count(Report.id))
        .filter(Report.organisation_id == organisation.id, Report.created_at >= month_start)
        .scalar()
        or 0
    )
    trial_days_left = None
    if subscription.status == "trialing" and subscription.trial_end:
        trial_days_left = max(0, (subscription.trial_end - datetime.utcnow()).days)
    return {
        "vehicles": int(vehicles),
        "vehicle_limit": plan.max_vehicles or None,
        "drivers": int(drivers),
        "driver_limit": plan.max_drivers or None,
        "events_this_month": int(events),
        "reports_this_month": int(reports),
        "plan_code": plan.code,
        "plan_name": plan.name,
        "subscription_status": subscription.status,
        "trial_days_left": trial_days_left,
    }


def _within_limit(count: int, limit: Optional[int]) -> bool:
    return limit is None or limit == 0 or count < limit


def assert_vehicle_quota(db: Session, organisation: Organisation) -> None:
    stats = usage(db, organisation)
    if not _within_limit(stats["vehicles"], stats["vehicle_limit"]):
        raise QuotaExceededError(
            f"Your {stats['plan_name']} plan allows {stats['vehicle_limit']} vehicles. Upgrade to add more."
        )


def assert_driver_quota(db: Session, organisation: Organisation) -> None:
    stats = usage(db, organisation)
    if not _within_limit(stats["drivers"], stats["driver_limit"]):
        raise QuotaExceededError(
            f"Your {stats['plan_name']} plan allows {stats['driver_limit']} drivers. Upgrade to add more."
        )


def upgrade(
    db: Session, organisation: Organisation, plan_code: str, seats: int = 1, actor=None
) -> tuple[Subscription, Payment]:
    plan = get_plan(db, plan_code)
    subscription = get_or_create_subscription(db, organisation)
    if subscription.plan_id == plan.id and subscription.status == "active":
        raise ConflictError("Organisation is already on this plan")

    now = datetime.utcnow()
    subscription.plan_id = plan.id
    subscription.seats = seats
    subscription.status = "active" if plan.price_monthly == 0 else "pending_payment"
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=30)
    subscription.cancel_at_period_end = False
    if plan.price_monthly == 0:
        subscription.status = "active"

    invoice = f"INV-{now.strftime('%Y%m')}-{organisation.id:04d}-{len(subscription.payments) + 1:03d}"
    payment = Payment(
        organisation_id=organisation.id,
        subscription_id=subscription.id,
        invoice_number=invoice,
        amount=plan.price_monthly * seats,
        currency=plan.currency,
        status="pending" if plan.price_monthly > 0 else "succeeded",
        provider="manual",
        description=f"{plan.name} plan - {seats} seat(s) - no payment provider configured",
    )
    db.add(payment)
    db.flush()
    return subscription, payment


def cancel(db: Session, organisation: Organisation) -> Subscription:
    subscription = get_or_create_subscription(db, organisation)
    subscription.cancel_at_period_end = True
    db.flush()
    return subscription


def billing_history(db: Session, organisation: Organisation, limit: int = 50) -> list[Payment]:
    return (
        db.query(Payment)
        .filter(Payment.organisation_id == organisation.id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
        .all()
    )
