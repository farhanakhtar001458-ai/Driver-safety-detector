"""AI model registry (governance: versions, metrics, limitations)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission, require_roles
from app.models import AIModelVersion, User
from app.schemas.common import MessageResponse
from app.schemas.saas import AIModelVersionIn, AIModelVersionOut
from app.services.audit import log_action

router = APIRouter(prefix="/ai-models", tags=["AI Models"])


@router.get("", response_model=list[AIModelVersionOut])
def list_models(user: User = Depends(require_permission("ai_models:read")), db: Session = Depends(get_db)):
    return [
        AIModelVersionOut.model_validate(model)
        for model in db.query(AIModelVersion).order_by(AIModelVersion.created_at.desc()).all()
    ]


@router.get("/{model_id}", response_model=AIModelVersionOut)
def get_model(model_id: int, user: User = Depends(require_permission("ai_models:read")), db: Session = Depends(get_db)):
    model = db.get(AIModelVersion, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model version not found")
    return AIModelVersionOut.model_validate(model)


@router.post("", response_model=AIModelVersionOut, status_code=201)
def register_model(
    payload: AIModelVersionIn,
    request: Request,
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    existing = db.query(AIModelVersion).filter(AIModelVersion.version == payload.version).first()
    if existing:
        raise HTTPException(status_code=409, detail="A model with this version already exists")
    model = AIModelVersion(created_by_id=user.id, **payload.model_dump())
    db.add(model)
    db.flush()
    log_action(
        db,
        user=user,
        action="ai_model.register",
        resource_type="ai_model",
        resource_id=model.id,
        detail={"version": model.version, "task": model.task},
        request=request,
    )
    return AIModelVersionOut.model_validate(model)


@router.patch("/{model_id}", response_model=AIModelVersionOut)
def update_model(
    model_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    model = db.get(AIModelVersion, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model version not found")
    for key in ("status", "description", "metrics", "limitations", "notes"):
        if key in payload and payload[key] is not None:
            setattr(model, key, payload[key])
    db.flush()
    log_action(
        db,
        user=user,
        action="ai_model.update",
        resource_type="ai_model",
        resource_id=model.id,
        detail={"fields": sorted(payload.keys())},
        request=request,
    )
    return AIModelVersionOut.model_validate(model)


@router.delete("/{model_id}", response_model=MessageResponse)
def retire_model(
    model_id: int,
    request: Request,
    user: User = Depends(require_roles("super_admin")),
    db: Session = Depends(get_db),
):
    model = db.get(AIModelVersion, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model version not found")
    model.status = "retired"
    db.flush()
    log_action(db, user=user, action="ai_model.retire", resource_type="ai_model", resource_id=model.id, request=request)
    return MessageResponse(message="Model version retired")
