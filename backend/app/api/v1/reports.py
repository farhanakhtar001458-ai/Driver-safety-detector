"""Reporting endpoints: summary analytics, PDF/CSV generation and download."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import Pagination, get_db, get_organisation, org_filter, require_permission
from app.models import Organisation, Report, User
from app.schemas.common import Paginated
from app.schemas.saas import ReportGenerateRequest, ReportOut, ReportSummary
from app.services import reports as report_service
from app.services.audit import log_action

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/types")
def report_types():
    return {
        "types": [
            {"code": code, "title": meta["title"], "default_days": meta["days"]}
            for code, meta in report_service.REPORT_TYPES.items()
        ],
        "formats": ["pdf", "csv"],
        "note": "Reports are generated from recorded and simulated telemetry. Simulated rows are labelled.",
    }


@router.get("/summary", response_model=ReportSummary)
def report_summary(
    report_type: str = Query(default="fleet_safety"),
    from_date: Optional[datetime] = Query(default=None, alias="from"),
    to_date: Optional[datetime] = Query(default=None, alias="to"),
    driver_id: Optional[int] = Query(default=None),
    vehicle_id: Optional[int] = Query(default=None),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("reports:read")),
    db: Session = Depends(get_db),
):
    if report_type not in report_service.REPORT_TYPES:
        raise HTTPException(status_code=422, detail="Unknown report type")
    effective_org = organisation_id if user.role == "super_admin" else user.organisation_id
    if not effective_org:
        raise HTTPException(status_code=400, detail="organisation_id is required for super administrators")
    summary = report_service.build_summary(
        db,
        effective_org,
        report_type=report_type,
        from_date=from_date,
        to_date=to_date,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
    )
    return ReportSummary(**summary)


@router.post("/generate", response_model=ReportOut, status_code=201)
def generate_report(
    payload: ReportGenerateRequest,
    request: Request,
    organisation: Organisation = Depends(get_organisation),
    user: User = Depends(require_permission("reports:generate")),
    db: Session = Depends(get_db),
):
    report = report_service.generate_report_file(
        db,
        organisation=organisation,
        user=user,
        report_type=payload.report_type,
        report_format=payload.format,
        title=payload.title,
        from_date=payload.from_date,
        to_date=payload.to_date,
        driver_id=payload.driver_id,
        vehicle_id=payload.vehicle_id,
    )
    log_action(
        db,
        user=user,
        action="report.generate",
        resource_type="report",
        resource_id=report.id,
        detail={"type": report.report_type, "format": report.format},
        request=request,
    )
    return ReportOut.model_validate(report)


@router.get("", response_model=Paginated[ReportOut])
def list_reports(
    pagination: Pagination = Depends(),
    report_type: Optional[str] = Query(default=None),
    organisation_id: Optional[int] = Query(default=None, alias="organisation_id"),
    user: User = Depends(require_permission("reports:read")),
    db: Session = Depends(get_db),
):
    query = org_filter(db.query(Report), Report, user, organisation_id)
    if report_type:
        query = query.filter(Report.report_type == report_type)
    total = query.count()
    rows = query.order_by(Report.created_at.desc()).offset(pagination.offset).limit(pagination.page_size).all()
    return Paginated[ReportOut].create(
        [ReportOut.model_validate(row) for row in rows], total, pagination.page, pagination.page_size
    )


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: int,
    user: User = Depends(require_permission("reports:read")),
    db: Session = Depends(get_db),
):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    from app.core.deps import ensure_org_access

    ensure_org_access(report.organisation_id, user)
    return ReportOut.model_validate(report)


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    user: User = Depends(require_permission("reports:read")),
    db: Session = Depends(get_db),
):
    import os

    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    from app.core.deps import ensure_org_access

    ensure_org_access(report.organisation_id, user)
    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Report file is no longer available")
    media_type = "application/pdf" if report.format == "pdf" else "text/csv"
    extension = "pdf" if report.format == "pdf" else "csv"
    return FileResponse(
        path=report.file_path,
        media_type=media_type,
        filename=f"{report.title.replace(' ', '_').lower()}.{extension}",
    )
