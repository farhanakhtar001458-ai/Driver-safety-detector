from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class ReportGenerateRequest(BaseModel):
    report_type: str = Field(default="fleet_safety")
    format: str = Field(default="pdf")
    title: Optional[str] = Field(default=None, max_length=200)
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None

    @field_validator("report_type")
    @classmethod
    def _type(cls, value: str) -> str:
        allowed = {
            "daily_safety", "weekly_safety", "monthly_safety", "driver_performance",
            "vehicle_performance", "fleet_safety", "incident", "maintenance", "risk_analysis",
        }
        if value not in allowed:
            raise ValueError(f"report_type must be one of {sorted(allowed)}")
        return value

    @field_validator("format")
    @classmethod
    def _format(cls, value: str) -> str:
        allowed = {"pdf", "csv"}
        if value not in allowed:
            raise ValueError("format must be pdf or csv")
        return value


class ReportOut(ORMModel):
    id: int
    report_type: str
    title: str
    params: Dict[str, Any]
    format: str
    status: str
    row_count: int
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime


class ReportSummary(BaseModel):
    report_type: str
    title: str
    period: Dict[str, Any]
    kpis: Dict[str, Any]
    charts: Dict[str, Any]
    tables: Dict[str, Any]
    generated_at: datetime
    disclaimer: str


class AuditLogOut(ORMModel):
    id: int
    organisation_id: Optional[int] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    detail: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    created_at: datetime


class AIModelVersionIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    version: str = Field(min_length=1, max_length=40)
    task: str
    status: str = "active"
    description: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
    trained_at: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        allowed = {"draft", "active", "deprecated", "retired"}
        if value not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return value


class AIModelVersionOut(ORMModel):
    id: int
    name: str
    version: str
    task: str
    status: str
    description: Optional[str] = None
    metrics: Dict[str, Any]
    limitations: List[str]
    trained_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime


class PlanUpgradeRequest(BaseModel):
    plan_code: str
    seats: int = Field(default=1, ge=1, le=500)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    driver_id: Optional[int] = None
    include_fleet_context: bool = True


class ChatResponse(BaseModel):
    reply: str
    mode: str  # llm | local
    suggestions: List[str] = Field(default_factory=list)
    grounding: Dict[str, Any] = Field(default_factory=dict)
    disclaimer: str
    model: Optional[str] = None
    latency_ms: Optional[int] = None


class CoachingReportOut(BaseModel):
    driver_id: int
    driver_name: str
    period_days: int
    generated_at: datetime
    summary: str
    strengths: List[str]
    focus_areas: List[Dict[str, Any]]
    recommendations: List[str]
    score_trend: List[Dict[str, Any]]
    disclaimer: str
