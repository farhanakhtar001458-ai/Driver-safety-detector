"""Service health and readiness endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, require_roles
from app.core.security import utcnow
from app.models import User
from app.services.simulator import simulator
from app.services.ws_hub import manager

router = APIRouter(tags=["Health"])


def _db_status(db: Session) -> str:
    try:
        db.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "unavailable"


def _redis_status() -> str:
    if not settings.REDIS_URL:
        return "not_configured"
    try:
        import redis

        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        client.ping()
        return "connected"
    except Exception:
        return "unavailable"


@router.get("/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "database": _db_status(db),
        "redis": _redis_status(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "demo_mode": settings.DEMO_MODE,
        "timestamp": utcnow().isoformat(),
    }


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    database = _db_status(db)
    return {
        "ready": database == "connected",
        "database": database,
        "checks": {
            "database": database,
            "redis": _redis_status(),
            "llm_configured": bool(settings.LLM_API_KEY),
            "smtp_configured": bool(settings.SMTP_HOST),
            "sms_configured": settings.SMS_PROVIDER not in {"", "none"},
        },
    }


@router.get("/health/details")
def health_details(user: User = Depends(require_roles("super_admin")), db: Session = Depends(get_db)):
    return {
        "database": _db_status(db),
        "redis": _redis_status(),
        "websocket": manager.stats(),
        "simulator": simulator.status(),
        "retention_days": settings.DATA_RETENTION_DAYS,
        "rate_limit_per_minute": settings.RATE_LIMIT_PER_MINUTE,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
