"""Report building and export (PDF / CSV).

PDFs are generated with ReportLab; CSVs with pandas. Both are written under
``data/reports`` and served through an authenticated download endpoint.
"""

from __future__ import annotations

import csv
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Driver,
    DriverScore,
    DrivingEvent,
    Incident,
    MaintenanceAlert,
    MaintenanceRecord,
    Organisation,
    Report,
    RiskAssessment,
    Trip,
    Vehicle,
)

REPORT_TYPES = {
    "daily_safety": {"title": "Daily Safety Report", "days": 1},
    "weekly_safety": {"title": "Weekly Safety Report", "days": 7},
    "monthly_safety": {"title": "Monthly Safety Report", "days": 30},
    "driver_performance": {"title": "Driver Performance Report", "days": 30},
    "vehicle_performance": {"title": "Vehicle Performance Report", "days": 30},
    "fleet_safety": {"title": "Fleet Safety Report", "days": 30},
    "incident": {"title": "Incident Report", "days": 90},
    "maintenance": {"title": "Maintenance Report", "days": 90},
    "risk_analysis": {"title": "Risk Analysis Report", "days": 90},
}

DISCLAIMER = (
    "This report was generated from recorded and simulated telemetry. Simulated data is labelled. "
    "Scores and risk levels support coaching and review; they do not predict accidents."
)


def _period(report_type: str, from_date: Optional[datetime], to_date: Optional[datetime]) -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    default_days = REPORT_TYPES.get(report_type, {"days": 30})["days"]
    end = to_date or now
    start = from_date or (end - timedelta(days=default_days))
    if start > end:
        start, end = end, start
    return start, end


def build_summary(
    db: Session,
    org_id: int,
    report_type: str = "fleet_safety",
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    driver_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
) -> dict[str, Any]:
    start, end = _period(report_type, from_date, to_date)
    event_query = db.query(DrivingEvent).filter(
        DrivingEvent.organisation_id == org_id,
        DrivingEvent.occurred_at >= start,
        DrivingEvent.occurred_at <= end,
    )
    trip_query = db.query(Trip).filter(
        Trip.organisation_id == org_id, Trip.start_time >= start, Trip.start_time <= end
    )
    if driver_id:
        event_query = event_query.filter(DrivingEvent.driver_id == driver_id)
        trip_query = trip_query.filter(Trip.driver_id == driver_id)
    if vehicle_id:
        event_query = event_query.filter(DrivingEvent.vehicle_id == vehicle_id)
        trip_query = trip_query.filter(Trip.vehicle_id == vehicle_id)
    events = event_query.all()
    trips = trip_query.all()

    distance = round(sum(float(t.distance_km or 0) for t in trips), 1)
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for event in events:
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
        by_severity[event.severity] = by_severity.get(event.severity, 0) + 1

    driver_ids = [driver_id] if driver_id else sorted({e.driver_id for e in events if e.driver_id})
    scores = (
        db.query(DriverScore)
        .filter(
            DriverScore.organisation_id == org_id,
            DriverScore.period == "weekly",
            DriverScore.period_start >= start - timedelta(days=7),
            DriverScore.period_start <= end,
        )
        .order_by(DriverScore.period_start.desc())
        .all()
    )
    score_map: dict[int, DriverScore] = {}
    for score in scores:
        if score.driver_id not in score_map:
            score_map[score.driver_id] = score

    incidents = (
        db.query(Incident)
        .filter(
            Incident.organisation_id == org_id,
            Incident.occurred_at >= start,
            Incident.occurred_at <= end,
        )
        .all()
    )
    maintenance = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.organisation_id == org_id,
            MaintenanceRecord.performed_at >= start,
            MaintenanceRecord.performed_at <= end,
        )
        .all()
    )
    alerts = (
        db.query(MaintenanceAlert)
        .filter(MaintenanceAlert.organisation_id == org_id, MaintenanceAlert.status == "open")
        .all()
    )
    risks = (
        db.query(RiskAssessment)
        .filter(
            RiskAssessment.organisation_id == org_id,
            RiskAssessment.created_at >= start,
            RiskAssessment.created_at <= end,
        )
        .all()
    )

    driver_rows = []
    for did in driver_ids:
        driver = db.get(Driver, did) if did else None
        if not driver:
            continue
        driver_events = [e for e in events if e.driver_id == did]
        score = score_map.get(did)
        driver_rows.append(
            {
                "driver": driver.full_name,
                "events": len(driver_events),
                "high_risk": sum(1 for e in driver_events if e.severity in {"high", "critical"}),
                "distance_km": round(sum(float(t.distance_km or 0) for t in trips if t.driver_id == did), 1),
                "score": score.overall_score if score else None,
                "incidents": sum(1 for i in incidents if i.driver_id == did),
            }
        )
    driver_rows.sort(key=lambda row: (row["score"] if row["score"] is not None else 999))

    vehicle_rows = []
    for vehicle in db.query(Vehicle).filter(Vehicle.organisation_id == org_id, Vehicle.is_archived.is_(False)).all():
        vehicle_events = [e for e in events if e.vehicle_id == vehicle.id]
        if vehicle_id and vehicle.id != vehicle_id:
            continue
        vehicle_rows.append(
            {
                "vehicle": vehicle.registration_number,
                "type": vehicle.vehicle_type,
                "status": vehicle.status,
                "events": len(vehicle_events),
                "distance_km": round(sum(float(t.distance_km or 0) for t in trips if t.vehicle_id == vehicle.id), 1),
                "mileage_km": round(vehicle.mileage_km, 1),
            }
        )

    trend: dict[str, dict[str, Any]] = {}
    days = max(1, (end - start).days)
    buckets = 7 if days <= 14 else 6
    for i in range(buckets):
        label = (start + timedelta(days=(days / buckets) * i)).strftime("%d %b")
        trend[label] = {"label": label, "events": 0, "high_risk": 0}
    for event in events:
        offset = (event.occurred_at - start).total_seconds() / max(1, (end - start).total_seconds())
        index = min(buckets - 1, int(offset * buckets))
        label = list(trend.keys())[index]
        trend[label]["events"] += 1
        if event.severity in {"high", "critical"}:
            trend[label]["high_risk"] += 1

    kpis = {
        "total_events": len(events),
        "high_risk_events": sum(1 for e in events if e.severity in {"high", "critical"}),
        "critical_events": by_severity["critical"],
        "events_per_100km": round(len(events) / max(distance, 10) * 100, 2),
        "distance_km": distance,
        "trips": len(trips),
        "avg_speed_kph": round(
            sum(float(t.average_speed_kph or 0) for t in trips) / len(trips), 1
        ) if trips else 0.0,
        "avg_score": round(
            sum(s.overall_score for s in score_map.values()) / len(score_map), 1
        ) if score_map else 0.0,
        "incidents": len([i for i in incidents if i.status != "false_alert"]),
        "open_maintenance_alerts": len(alerts),
        "maintenance_records": len(maintenance),
        "maintenance_cost": round(sum(float(m.cost or 0) for m in maintenance), 2),
        "risk_assessments": len(risks),
        "high_risk_drivers": len([r for r in risks if r.risk_level in {"high", "critical"}]),
        "simulated_events": sum(1 for e in events if e.is_simulated),
        "simulated_share_pct": round(sum(1 for e in events if e.is_simulated) / len(events) * 100, 1)
        if events
        else 0.0,
    }

    charts = {
        "trend": list(trend.values()),
        "events_by_type": [{"type": k, "count": v} for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])],
        "events_by_severity": [{"severity": k, "count": v} for k, v in by_severity.items()],
    }

    tables = {
        "drivers": driver_rows[:25],
        "vehicles": vehicle_rows[:25],
        "incidents": [
            {
                "occurred_at": i.occurred_at.strftime("%Y-%m-%d %H:%M"),
                "title": i.title,
                "severity": i.severity,
                "status": i.status,
                "driver": i.driver.full_name if i.driver else "-",
            }
            for i in sorted(incidents, key=lambda x: x.occurred_at, reverse=True)[:25]
        ],
        "maintenance": [
            {
                "date": m.performed_at.strftime("%Y-%m-%d"),
                "vehicle": m.vehicle.registration_number if m.vehicle else "-",
                "type": m.record_type,
                "title": m.title,
                "cost": m.cost,
                "status": m.status,
            }
            for m in sorted(maintenance, key=lambda x: x.performed_at, reverse=True)[:25]
        ],
        "alerts": [
            {
                "title": a.title,
                "vehicle": a.vehicle.registration_number if a.vehicle else "-",
                "severity": a.severity,
                "type": a.alert_type,
            }
            for a in alerts[:25]
        ],
        "risks": [
            {
                "driver": r.driver.full_name if r.driver else "-",
                "level": r.risk_level,
                "score": round(r.risk_score, 3),
                "confidence": r.confidence,
                "date": r.created_at.strftime("%Y-%m-%d"),
            }
            for r in sorted(risks, key=lambda x: x.created_at, reverse=True)[:25]
        ],
    }

    return {
        "report_type": report_type,
        "title": REPORT_TYPES.get(report_type, {"title": "Safety Report"})["title"],
        "period": {"from": start.isoformat() + "Z", "to": end.isoformat() + "Z", "days": days},
        "filters": {"driver_id": driver_id, "vehicle_id": vehicle_id},
        "kpis": kpis,
        "charts": charts,
        "tables": tables,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "disclaimer": DISCLAIMER,
    }


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------
def export_csv(summary: dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["SafeWay AI - " + summary["title"]])
        writer.writerow(["Period", f"{summary['period']['from']} to {summary['period']['to']}"])
        writer.writerow(["Generated", summary["generated_at"]])
        writer.writerow([])
        writer.writerow(["Section", "Metric", "Value"])
        for key, value in summary["kpis"].items():
            writer.writerow(["KPI", key, value])
        writer.writerow([])
        writer.writerow(["Chart", "Label", "Count"])
        for chart_name, rows in summary["charts"].items():
            for row in rows:
                label = row.get("label") or row.get("type") or row.get("severity")
                count = row.get("count", row.get("events", ""))
                writer.writerow([chart_name, label, count])
        writer.writerow([])
        for table_name, rows in summary["tables"].items():
            if not rows:
                continue
            writer.writerow([f"Table: {table_name}"])
            headers = list(rows[0].keys())
            writer.writerow(headers)
            for row in rows:
                writer.writerow([row.get(header, "") for header in headers])
            writer.writerow([])
        writer.writerow([summary["disclaimer"]])


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def export_pdf(summary: dict[str, Any], path: str, organisation_name: str) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc = SimpleDocTemplate(path, pagesize=A4, title=summary["title"], author="SafeWay AI")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontSize=20, leading=24, textColor=colors.HexColor("#0f172a"))
    heading_style = ParagraphStyle("H2", parent=styles["Heading2"], textColor=colors.HexColor("#0f766e"), spaceBefore=14, spaceAfter=6)
    small_style = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=11, textColor=colors.HexColor("#475569"))
    body_style = styles["BodyText"]

    story = [Paragraph(summary["title"], title_style)]
    story.append(Paragraph(f"{organisation_name} · {summary['period']['from'][:10]} to {summary['period']['to'][:10]}", small_style))
    story.append(Paragraph(f"Generated {summary['generated_at']}", small_style))
    story.append(Spacer(1, 8 * mm))

    kpi_data = [["Metric", "Value"]] + [[key.replace("_", " ").title(), str(value)] for key, value in summary["kpis"].items()]
    kpi_table = Table(kpi_data, colWidths=[95 * mm, 55 * mm], hAlign="LEFT")
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Events by type", heading_style))
    type_rows = [["Event type", "Count"]] + [
        [row["type"].replace("_", " ").title(), str(row["count"])] for row in summary["charts"]["events_by_type"]
    ]
    if len(type_rows) > 1:
        table = Table(type_rows, colWidths=[95 * mm, 55 * mm], hAlign="LEFT")
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
        story.append(table)

    story.append(Paragraph("Driver performance", heading_style))
    driver_rows = summary["tables"]["drivers"]
    if driver_rows:
        data = [["Driver", "Events", "High risk", "Distance (km)", "Score", "Incidents"]] + [
            [
                row["driver"],
                str(row["events"]),
                str(row["high_risk"]),
                str(row["distance_km"]),
                str(row["score"] if row["score"] is not None else "-"),
                str(row["incidents"]),
            ]
            for row in driver_rows
        ]
        table = Table(data, colWidths=[48 * mm, 18 * mm, 20 * mm, 26 * mm, 18 * mm, 20 * mm], repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ]
            )
        )
        story.append(table)

    story.append(Paragraph("Incidents", heading_style))
    incident_rows = summary["tables"]["incidents"]
    if incident_rows:
        data = [["Date", "Incident", "Severity", "Status"]] + [
            [row["occurred_at"], row["title"], row["severity"], row["status"]] for row in incident_rows[:12]
        ]
        table = Table(data, colWidths=[30 * mm, 82 * mm, 22 * mm, 26 * mm], repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("No incidents recorded in the selected period.", body_style))

    story.append(Paragraph("Method and limitations", heading_style))
    story.append(Paragraph(summary["disclaimer"], small_style))
    story.append(
        Paragraph(
            "Scores are calculated from event rates per 100 km. Risk levels are triage priorities produced by a "
            "gradient-boosted classifier combined with transparent rules. Camera-derived observations are treated as "
            "low-confidence unless verified by a reviewer. No output in this report predicts the time or occurrence of an accident.",
            small_style,
        )
    )

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(18 * mm, 12 * mm, "SafeWay AI - Driving Safety Management Platform")
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)


def generate_report_file(
    db: Session,
    *,
    organisation: Organisation,
    user,
    report_type: str,
    report_format: str,
    title: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    driver_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
) -> Report:
    summary = build_summary(
        db,
        organisation.id,
        report_type=report_type,
        from_date=from_date,
        to_date=to_date,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
    )
    safe_name = f"{report_type}_{uuid.uuid4().hex[:8]}.{report_format}"
    folder = os.path.join(os.getcwd(), "data", "reports")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, safe_name)
    report_title = title or summary["title"]
    if report_format == "csv":
        export_csv(summary, path)
    else:
        export_pdf(summary, path, organisation.name)
    report = Report(
        organisation_id=organisation.id,
        generated_by_id=user.id if user else None,
        report_type=report_type,
        title=report_title,
        params={
            "from": summary["period"]["from"],
            "to": summary["period"]["to"],
            "driver_id": driver_id,
            "vehicle_id": vehicle_id,
        },
        format=report_format,
        file_path=path,
        status="completed",
        row_count=sum(len(rows) for rows in summary["tables"].values()),
    )
    db.add(report)
    db.flush()
    return report
