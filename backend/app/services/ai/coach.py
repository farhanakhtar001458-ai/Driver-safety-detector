"""AI coaching assistant.

Two modes:
* ``llm`` — an OpenAI-compatible chat completion API called **from the backend**.
  The API key never reaches the browser.
* ``local`` — a deterministic, telemetry-grounded coach used when no LLM key is
  configured, or when the provider call fails.

Both modes are restricted to driving-safety guidance. Neither mode diagnoses
medical conditions, declares legal violations or predicts accidents.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    DrivingEvent,
    Driver,
    DriverScore,
    Incident,
    MaintenanceAlert,
    Notification,
    Organisation,
    RiskAssessment,
    Trip,
    Vehicle,
    VehicleHealthReading,
)

DISCLAIMER = (
    "SafeWay Coach provides general road-safety guidance based on recorded telemetry. "
    "It is not a medical, legal or emergency service, and it cannot predict accidents. "
    "For emergencies contact your local emergency number."
)

SAFETY_SYSTEM_PROMPT = f"""You are SafeWay Coach, an AI driving-safety assistant for a fleet management platform.
Rules you must always follow:
1. Use ONLY the telemetry context provided by the user's message. If a value is missing, say it is unavailable.
2. Never claim to predict when or whether an accident will happen. Never guarantee safety outcomes.
3. Never diagnose medical conditions, fatigue disorders, or intoxication. Describe observations only.
4. Never state that a driver committed a legal violation. Use phrases like "recorded speeding event" or "flagged behaviour".
5. Treat camera-derived observations as low-confidence unless verified by a human reviewer.
6. Give practical, specific coaching advice and suggest a follow-up action.
7. Be concise and structured. Use short paragraphs or bullets. No more than 180 words unless asked for a report.
{DISCLAIMER}"""

_FALLBACK_SUGGESTIONS = [
    "Why did my safety score change this week?",
    "What should I focus on to improve?",
    "Summarise my recent driving events.",
    "Which vehicles need maintenance attention?",
]


# --------------------------------------------------------------------------
# Context building
# --------------------------------------------------------------------------
def _period_stats(db: Session, driver_id: int, days: int) -> dict[str, Any]:
    start = datetime.utcnow() - timedelta(days=days)
    events = (
        db.query(DrivingEvent)
        .filter(DrivingEvent.driver_id == driver_id, DrivingEvent.occurred_at >= start)
        .all()
    )
    distance = float(
        db.query(func.coalesce(func.sum(Trip.distance_km), 0.0))
        .filter(Trip.driver_id == driver_id, Trip.start_time >= start)
        .scalar()
        or 0.0
    )
    by_type: dict[str, int] = {}
    for event in events:
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
    return {
        "days": days,
        "events": len(events),
        "high_risk": sum(1 for e in events if e.severity in {"high", "critical"}),
        "distance_km": round(distance, 1),
        "by_type": by_type,
        "events_per_100km": round(len(events) / max(distance, 10) * 100, 2),
    }


def build_driver_context(db: Session, driver: Driver, include_fleet: bool = True) -> dict[str, Any]:
    scores = (
        db.query(DriverScore)
        .filter(DriverScore.driver_id == driver.id, DriverScore.period == "weekly")
        .order_by(DriverScore.period_start.desc())
        .limit(4)
        .all()
    )
    latest = scores[0] if scores else None
    previous = scores[1] if len(scores) > 1 else None
    delta = None
    if latest and previous:
        delta = round(latest.overall_score - previous.overall_score, 1)
    risk = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.driver_id == driver.id)
        .order_by(RiskAssessment.created_at.desc())
        .first()
    )
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.assigned_driver_id == driver.id, Vehicle.is_archived.is_(False))
        .first()
    )
    incidents = (
        db.query(func.count(Incident.id))
        .filter(Incident.driver_id == driver.id, Incident.status != "false_alert")
        .scalar()
        or 0
    )
    context: dict[str, Any] = {
        "driver": {
            "id": driver.id,
            "name": driver.full_name,
            "status": driver.status,
            "years_experience": driver.years_experience,
            "licence_expiry": driver.licence_expiry.isoformat() if driver.licence_expiry else None,
        },
        "score": {
            "latest_weekly": latest.overall_score if latest else None,
            "previous_weekly": previous.overall_score if previous else None,
            "delta": delta,
            "subscores": {
                "speed": latest.speed_score if latest else None,
                "braking": latest.braking_score if latest else None,
                "acceleration": latest.acceleration_score if latest else None,
                "cornering": latest.cornering_score if latest else None,
                "consistency": latest.consistency_score if latest else None,
            }
            if latest
            else {},
            "confidence": latest.confidence if latest else None,
        },
        "last_30_days": _period_stats(db, driver.id, 30),
        "last_7_days": _period_stats(db, driver.id, 7),
        "risk": {
            "level": risk.risk_level if risk else "not_assessed",
            "score": risk.risk_score if risk else None,
            "indicators": [i.get("label") for i in (risk.indicators or [])][:4] if risk else [],
        }
        if risk
        else {"level": "not_assessed"},
        "incidents_total": int(incidents),
        "vehicle": {
            "registration": vehicle.registration_number if vehicle else None,
            "model": f"{vehicle.manufacturer} {vehicle.model}" if vehicle else None,
            "status": vehicle.status if vehicle else None,
        }
        if vehicle
        else None,
    }
    if include_fleet and driver.organisation_id:
        org = db.get(Organisation, driver.organisation_id)
        if org:
            fleet_events = (
                db.query(func.count(DrivingEvent.id))
                .filter(DrivingEvent.organisation_id == org.id)
                .scalar()
                or 0
            )
            fleet_drivers = (
                db.query(func.count(Driver.id)).filter(Driver.organisation_id == org.id).scalar() or 0
            )
            fleet_vehicles = (
                db.query(func.count(Vehicle.id))
                .filter(Vehicle.organisation_id == org.id, Vehicle.is_archived.is_(False))
                .scalar()
                or 0
            )
            open_alerts = (
                db.query(func.count(MaintenanceAlert.id))
                .filter(MaintenanceAlert.organisation_id == org.id, MaintenanceAlert.status == "open")
                .scalar()
                or 0
            )
            context["fleet"] = {
                "organisation": org.name,
                "vehicles": fleet_vehicles,
                "drivers": fleet_drivers,
                "events": fleet_events,
                "open_maintenance_alerts": open_alerts,
            }
    return context


# --------------------------------------------------------------------------
# Local (deterministic) coach
# --------------------------------------------------------------------------
def _fmt(value: Optional[float], suffix: str = "") -> str:
    if value is None:
        return "unavailable"
    return f"{value:.1f}{suffix}" if isinstance(value, float) else f"{value}{suffix}"


def local_reply(message: str, context: dict[str, Any]) -> tuple[str, list[str], dict[str, Any]]:
    text = message.lower()
    score = context.get("score", {})
    stats = context.get("last_30_days", {})
    week = context.get("last_7_days", {})
    risk = context.get("risk", {})
    driver_name = context.get("driver", {}).get("name", "driver")
    first_name = driver_name.split()[0] if driver_name else "there"
    suggestions = [
        "What should I focus on to improve?",
        "Summarise my recent driving events.",
        "Explain how my safety score is calculated.",
    ]
    grounding: dict[str, Any] = {"mode": "local", "context_used": []}

    if re.search(r"\b(hi|hello|hey|good morning|good evening)\b", text):
        return (
            f"Hello {first_name}! I'm SafeWay Coach. I can explain your safety score, summarise recent events, "
            "suggest coaching focus areas and answer questions about your vehicle. What would you like to review?",
            suggestions,
            grounding,
        )

    if re.search(r"score.*(drop|decreas|down|fall|chang)|why.*score|score.*(this|last) week", text):
        latest = score.get("latest_weekly")
        previous = score.get("previous_weekly")
        delta = score.get("delta")
        grounding["context_used"] = ["weekly_score", "weekly_delta", "event_counts_7d"]
        if latest is None:
            return (
                "I don't have a recent weekly score for you yet. Scores are calculated after at least one recorded trip. "
                "Once telemetry is available I can explain exactly what moved your score.",
                suggestions,
                grounding,
            )
        direction = "decreased" if (delta or 0) < 0 else "increased" if (delta or 0) > 0 else "stayed stable"
        parts = [
            f"{first_name}, your weekly safety score {direction} by {abs(delta or 0):.1f} points, from "
            f"{_fmt(previous)} to {_fmt(latest)}."
        ]
        top_types = sorted(week.get("by_type", {}).items(), key=lambda kv: kv[1], reverse=True)[:2]
        if top_types:
            description = ", ".join(f"{count} {name.replace('_', ' ')} event(s)" for name, count in top_types)
            parts.append(f"The main contributors in the last 7 days were {description}.")
        elif week.get("events", 0) == 0:
            parts.append("No safety events were recorded in the last 7 days, so the change is mostly driven by the earlier week.")
        subscores = score.get("subscores", {})
        weak = sorted(
            [(k, v) for k, v in subscores.items() if isinstance(v, (int, float))], key=lambda kv: kv[1]
        )[:2]
        if weak:
            parts.append(
                "The lowest categories are "
                + ", ".join(f"{name.replace('_', ' ')} ({_fmt(value)})" for name, value in weak)
                + "."
            )
        parts.append(
            "Follow posted speed limits, brake progressively and keep a steady speed. Review your top event type first — "
            "that usually moves the score fastest."
        )
        return (" ".join(parts), suggestions, grounding)

    if re.search(r"improve|better|coach|recommend|advice|focus", text):
        subscores = score.get("subscores", {}) or {}
        weak = sorted(
            [(k, v) for k, v in subscores.items() if isinstance(v, (int, float))], key=lambda kv: kv[1]
        )[:3]
        lines = [f"Here's a short coaching plan for you, {first_name}:"]
        if weak:
            lines.append(
                "Focus first on "
                + ", ".join(f"{name.replace('_', ' ')} ({_fmt(value)}/100)" for name, value in weak)
                + "."
            )
        for name, _ in weak:
            advice = {
                "speed": "Keep a steady pace and use speed alerts; leave earlier instead of speeding.",
                "braking": "Increase following distance and start braking earlier at signals.",
                "acceleration": "Accelerate smoothly, especially when the vehicle is loaded.",
                "cornering": "Slow before corners and avoid braking mid-turn.",
                "consistency": "Reduce speed variation by anticipating traffic ahead.",
            }.get(name)
            if advice:
                lines.append(f"- {advice}")
        top = sorted(stats.get("by_type", {}).items(), key=lambda kv: kv[1], reverse=True)[:1]
        if top:
            lines.append(
                f"In the last 30 days you recorded {top[0][1]} {top[0][0].replace('_', ' ')} event(s) over "
                f"{_fmt(stats.get('distance_km'), ' km')}."
            )
        lines.append("Recheck your score next week and compare the trend rather than a single day.")
        grounding["context_used"] = ["subscores", "event_counts_30d", "distance_30d"]
        return ("\n".join(lines), suggestions, grounding)

    if re.search(r"speed|limit|fast", text):
        speeding = week.get("by_type", {}).get("speeding", 0)
        total_30 = stats.get("by_type", {}).get("speeding", 0)
        grounding["context_used"] = ["speeding_events_7d", "speeding_events_30d"]
        return (
            f"You have {speeding} recorded speeding event(s) in the last 7 days and {total_30} in the last 30 days. "
            "Speeding is the strongest lever on your score because it affects the speed-management and consistency categories. "
            "Keep a steady speed, use the posted limit as the ceiling and build in extra time for journeys so you don't need to catch up.",
            suggestions,
            grounding,
        )

    if re.search(r"brak|stop|harsh", text):
        braking = stats.get("by_type", {}).get("harsh_braking", 0)
        grounding["context_used"] = ["harsh_braking_30d", "braking_score"]
        return (
            f"You recorded {braking} harsh-braking event(s) in the last 30 days, and your braking score is "
            f"{_fmt(score.get('subscores', {}).get('braking'))}. Harsh braking usually follows too little following distance or late "
            "anticipation of signals. Try the four-second rule in dry conditions and begin slowing earlier when you see a junction ahead.",
            suggestions,
            grounding,
        )

    if re.search(r"risk|danger|safe|dangerous", text):
        level = risk.get("level", "not_assessed")
        indicators = risk.get("indicators", [])
        grounding["context_used"] = ["latest_risk_assessment"]
        text_out = f"Your latest risk assessment is **{level}**" + (
            f" with risk score {risk.get('score'):.2f}." if risk.get("score") is not None else "."
        )
        if indicators:
            text_out += " The main indicators were: " + "; ".join(indicators) + "."
        text_out += (
            " This is a review priority, not a prediction of an accident. The most effective actions are usually coaching "
            "and vehicle maintenance rather than restrictions."
        )
        return (text_out, suggestions, grounding)

    if re.search(r"vehicle|mainten|service|fault|tyre|engine|health", text):
        vehicle = context.get("vehicle") or {}
        grounding["context_used"] = ["vehicle", "maintenance_alerts"]
        if not vehicle:
            return (
                "No vehicle is currently assigned to you, so I can't review its condition. Ask your fleet manager to assign one.",
                suggestions,
                grounding,
            )
        return (
            f"Your assigned vehicle is {vehicle.get('registration')} ({vehicle.get('model')}), status: {vehicle.get('status')}. "
            "Check tyre pressure and tread weekly, watch for new warning lights, and report brake noise or pulling immediately. "
            "I can also review open maintenance alerts if you ask about fleet maintenance.",
            suggestions,
            grounding,
        )

    if re.search(r"event|history|drive|driving|summar", text):
        by_type = stats.get("by_type", {})
        top = sorted(by_type.items(), key=lambda kv: kv[1], reverse=True)[:4]
        grounding["context_used"] = ["events_30d", "distance_30d"]
        if not top:
            return (
                f"No safety events were recorded in the last {stats.get('days', 30)} days over "
                f"{_fmt(stats.get('distance_km'), ' km')}. That's a good sign — keep it up.",
                suggestions,
                grounding,
            )
        listing = ", ".join(f"{count} {name.replace('_', ' ')}" for name, count in top)
        return (
            f"In the last {stats.get('days', 30)} days you recorded {stats.get('events')} event(s) over "
            f"{_fmt(stats.get('distance_km'), ' km')} ({stats.get('events_per_100km')} per 100 km). Breakdown: {listing}. "
            f"Your current weekly score is {_fmt(score.get('latest_weekly'))}.",
            suggestions,
            grounding,
        )

    if re.search(r"fleet|team|organisation|company", text):
        fleet = context.get("fleet") or {}
        grounding["context_used"] = ["fleet_summary"]
        if not fleet:
            return ("I don't have fleet context available for this account.", suggestions, grounding)
        return (
            f"{fleet.get('organisation')} currently has {fleet.get('vehicles')} vehicle(s) and {fleet.get('drivers')} driver(s) "
            f"on the platform, with {fleet.get('events')} recorded safety event(s) in total and "
            f"{fleet.get('open_maintenance_alerts')} open maintenance alert(s). Prioritise drivers with repeated speeding or "
            "harsh-braking patterns, and clear maintenance alerts before they become roadside failures.",
            suggestions,
            grounding,
        )

    if re.search(r"how.*(score|calculated|work)|score.*calc|weight", text):
        grounding["context_used"] = ["scoring_method"]
        return (
            "Your safety score is a 0-100 weighted average of six categories: speed management (22%), braking (18%), "
            "acceleration (15%), cornering (15%), seatbelt compliance (12%) and driving consistency (18%). Each category "
            "starts at 100 and decays based on events per 100 km. Categories with no sensor data are excluded and the "
            "remaining weights are renormalised, so missing data doesn't unfairly reduce your score. Scores describe recorded "
            "behaviour, not crash probability.",
            suggestions,
            grounding,
        )

    grounding["context_used"] = ["capabilities"]
    return (
        f"I can help with your safety score, recent events, coaching priorities, risk assessment and vehicle maintenance. "
        f"Try asking: 'Why did my safety score decrease this week?' or 'What should I focus on to improve?' "
        "I answer from your recorded telemetry, and I don't make medical or legal judgements.",
        _FALLBACK_SUGGESTIONS,
        grounding,
    )


# --------------------------------------------------------------------------
# LLM coach
# --------------------------------------------------------------------------
def llm_reply(message: str, context: dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[int]]:
    if not settings.LLM_API_KEY:
        return None, None, None
    payload = {
        "model": settings.LLM_MODEL,
        "temperature": 0.3,
        "max_tokens": 500,
        "messages": [
            {"role": "system", "content": SAFETY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Telemetry context (JSON):\n"
                    + repr(context)
                    + f"\n\nDriver question: {message}\n"
                    "Answer using only this context."
                ),
            },
        ],
    }
    started = time.time()
    try:
        with httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content, settings.LLM_MODEL, int((time.time() - started) * 1000)
    except Exception:  # provider down, quota exhausted, network blocked, malformed response
        return None, None, None


def chat(
    db: Session,
    user,
    message: str,
    driver_id: Optional[int] = None,
    include_fleet_context: bool = True,
) -> dict[str, Any]:
    from app.core.rbac import UserRole

    driver: Optional[Driver] = None
    if driver_id:
        driver = db.get(Driver, driver_id)
        if driver and user.role != UserRole.SUPER_ADMIN.value and driver.organisation_id != user.organisation_id:
            raise PermissionError("Driver belongs to another organisation")
    if driver is None and user.role == UserRole.DRIVER.value:
        driver = (
            db.query(Driver)
            .filter(Driver.user_id == user.id)
            .first()
        )

    context: dict[str, Any]
    if driver:
        context = build_driver_context(db, driver, include_fleet=include_fleet_context)
    else:
        # Fleet-level context for managers / safety officers.
        org_id = user.organisation_id
        context = {"fleet": {}}
        if org_id:
            org = db.get(Organisation, org_id)
            if org:
                context["fleet"] = {
                    "organisation": org.name,
                    "vehicles": db.query(func.count(Vehicle.id))
                    .filter(Vehicle.organisation_id == org_id, Vehicle.is_archived.is_(False))
                    .scalar()
                    or 0,
                    "drivers": db.query(func.count(Driver.id)).filter(Driver.organisation_id == org_id).scalar() or 0,
                    "events": db.query(func.count(DrivingEvent.id))
                    .filter(DrivingEvent.organisation_id == org_id)
                    .scalar()
                    or 0,
                    "open_maintenance_alerts": db.query(func.count(MaintenanceAlert.id))
                    .filter(MaintenanceAlert.organisation_id == org_id, MaintenanceAlert.status == "open")
                    .scalar()
                    or 0,
                }
        if driver_id is None and not context.get("fleet"):
            context = {"fleet": {}}

    reply, model, latency = llm_reply(message, context)
    mode = "llm"
    suggestions: list[str] = []
    grounding: dict[str, Any] = {"mode": "llm", "context_keys": sorted(context.keys())}
    if reply is None:
        reply, suggestions, grounding = local_reply(message, context)
        mode = "local"
    else:
        suggestions = [
            "What should I focus on to improve?",
            "Summarise my recent driving events.",
            "Explain my risk assessment.",
        ]

    # Store the conversation as a system notification for auditability.
    if user.organisation_id:
        db.add(
            Notification(
                organisation_id=user.organisation_id,
                user_id=user.id,
                type="coaching",
                title="AI coach conversation",
                message=f"Question: {message[:180]}",
                priority="low",
                channel="in_app",
                related_type="assistant",
                delivery_status="delivered",
            )
        )
        db.flush()

    return {
        "reply": reply,
        "mode": mode,
        "suggestions": suggestions,
        "grounding": grounding,
        "disclaimer": DISCLAIMER,
        "model": model,
        "latency_ms": latency,
    }


# --------------------------------------------------------------------------
# Weekly coaching report
# --------------------------------------------------------------------------
def generate_coaching_report(db: Session, driver_id: int, days: int = 30) -> dict[str, Any]:
    driver = db.get(Driver, driver_id)
    if not driver:
        raise LookupError("Driver not found")
    context = build_driver_context(db, driver, include_fleet=False)
    scores = (
        db.query(DriverScore)
        .filter(DriverScore.driver_id == driver.id, DriverScore.period == "weekly")
        .order_by(DriverScore.period_start.asc())
        .limit(12)
        .all()
    )
    subscores = context.get("score", {}).get("subscores", {}) or {}
    strengths = [
        f"{name.replace('_', ' ').title()} ({value:.0f}/100)"
        for name, value in sorted(
            [(k, v) for k, v in subscores.items() if isinstance(v, (int, float))], key=lambda kv: -kv[1]
        )[:2]
    ]
    focus = sorted(
        [(k, v) for k, v in subscores.items() if isinstance(v, (int, float))], key=lambda kv: kv[1]
    )[:3]
    focus_areas = []
    for name, value in focus:
        if value < 85:
            focus_areas.append(
                {
                    "category": name.replace("_", " ").title(),
                    "score": value,
                    "advice": {
                        "speed": "Keep a steady pace and observe posted limits.",
                        "braking": "Increase following distance and brake progressively.",
                        "acceleration": "Smooth acceleration, especially when loaded.",
                        "cornering": "Reduce speed before corners.",
                        "consistency": "Anticipate traffic to reduce speed variation.",
                        "seatbelt": "Complete a pre-trip seatbelt check.",
                    }.get(name, "Review recent events with your manager."),
                }
            )
    by_type = context.get("last_30_days", {}).get("by_type", {})
    top_event = max(by_type.items(), key=lambda kv: kv[1])[0] if by_type else None
    summary = (
        f"{driver.full_name}'s weekly score is {context['score'].get('latest_weekly') or 'not yet available'}. "
        f"Over the last {days} days there were {context['last_30_days']['events']} recorded events across "
        f"{context['last_30_days']['distance_km']} km."
    )
    if top_event:
        summary += f" The most frequent event type was {top_event.replace('_', ' ')}."
    return {
        "driver_id": driver.id,
        "driver_name": driver.full_name,
        "period_days": days,
        "generated_at": datetime.utcnow(),
        "summary": summary,
        "strengths": strengths or ["No stable category data available yet"],
        "focus_areas": focus_areas,
        "recommendations": [
            "Review the top event type with the driver in a 15-minute coaching session.",
            "Set one measurable goal for the next week (for example, zero speeding events).",
            "Re-check the score trend after seven days and record the outcome.",
        ],
        "score_trend": [
            {"period": s.period_start.strftime("%d %b"), "score": s.overall_score} for s in scores
        ],
        "disclaimer": DISCLAIMER,
    }
