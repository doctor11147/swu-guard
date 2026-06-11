"""通行日志相关 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AccessDecision = Literal["granted", "rejected", "spoof", "no_face"]


class AccessLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    gate_id: int | None
    matched_person_id: int | None
    visitor_appointment_id: int | None = None
    score: float | None
    spoof_score: float | None
    decision: AccessDecision
    snapshot_path: str | None
    detail: str | None
    # 联表展示字段（路由层填充）
    gate_name: str | None = None
    person_name: str | None = None
    person_external_id: str | None = None


class AccessLogStatsOut(BaseModel):
    """聚合统计响应：用于 dashboard / 大屏。"""

    by_day: list[dict] = Field(default_factory=list, description="[{date, total, granted, rejected, spoof, no_face}]")
    by_hour: list[dict] = Field(default_factory=list, description="[{hour, total}]，最近 24h")
    by_gate: list[dict] = Field(default_factory=list, description="[{gate_id, gate_name, total}]")
    by_decision: dict = Field(default_factory=dict, description="{granted, rejected, spoof, no_face}")
    today_total: int = 0
    week_total: int = 0
