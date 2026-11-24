"""AI coaching assistant endpoints.

The LLM is called server-side only. If no key is configured the assistant falls
back to a deterministic local coach that answers from the driver's telemetry.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, require_permission
from app.models import Driver, User
from app.schemas.common import MessageResponse
from app.schemas.saas import ChatRequest, ChatResponse, CoachingReportOut
from app.services.ai import coach
from app.services.audit import log_action

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


@router.get("/capabilities")
def capabilities(user: User = Depends(require_permission("assistant:use"))):
    return {
        "mode": "llm" if settings.LLM_API_KEY else "local",
        "model": settings.LLM_MODEL if settings.LLM_API_KEY else None,
        "can_answer_about": [
            "safety score changes and category breakdowns",
            "recent driving events and frequency",
            "coaching priorities and training suggestions",
            "risk assessment explanations",
            "vehicle maintenance basics",
            "fleet safety questions for managers",
        ],
        "will_not_do": [
            "diagnose medical conditions or fatigue disorders",
            "declare legal violations",
            "predict accidents or guarantee safety outcomes",
            "contact emergency services",
        ],
        "disclaimer": coach.DISCLAIMER,
    }


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    user: User = Depends(require_permission("assistant:use")),
    db: Session = Depends(get_db),
):
    try:
        result = coach.chat(
            db,
            user,
            payload.message.strip(),
            driver_id=payload.driver_id,
            include_fleet_context=payload.include_fleet_context,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Driver belongs to another organisation")
    log_action(
        db,
        user=user,
        action="assistant.chat",
        resource_type="assistant",
        detail={"mode": result["mode"], "length": len(payload.message)},
        request=request,
    )
    return ChatResponse(**result)


@router.post("/coaching-report/{driver_id}", response_model=CoachingReportOut)
def coaching_report(
    driver_id: int,
    request: Request,
    days: int = Query(default=30, ge=7, le=90),
    user: User = Depends(require_permission("assistant:use")),
    db: Session = Depends(get_db),
):
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    if user.role != "super_admin" and driver.organisation_id != user.organisation_id:
        raise HTTPException(status_code=404, detail="Driver not found")
    result = coach.generate_coaching_report(db, driver.id, days)
    log_action(
        db,
        user=user,
        action="assistant.coaching_report",
        resource_type="driver",
        resource_id=driver.id,
        request=request,
    )
    return CoachingReportOut(**result)


@router.post("/feedback", response_model=MessageResponse)
def feedback(
    payload: dict,
    user: User = Depends(require_permission("assistant:use")),
    db: Session = Depends(get_db),
):
    """Store thumbs up/down for coaching quality review (no PII beyond user id)."""
    rating = payload.get("rating")
    if rating not in {"up", "down"}:
        raise HTTPException(status_code=422, detail="rating must be 'up' or 'down'")
    log_action(
        db,
        user=user,
        action="assistant.feedback",
        resource_type="assistant",
        detail={"rating": rating, "message_id": payload.get("message_id")},
    )
    return MessageResponse(message="Feedback recorded")
