"""系统配置 / dashboard 相关 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config_key: str
    value_json: dict
    description: str | None
    updated_at: datetime


class ConfigUpdateIn(BaseModel):
    """``value`` 直接是配置值（数字、字符串、bool、嵌套对象皆可）。

    服务端会包装为 ``{"value": <value>}`` 后写入，与 schema.sql 中的种子格式一致。
    """

    value: Any


class DashboardOut(BaseModel):
    """大屏 / 主面板聚合数据。"""

    school: dict = Field(default_factory=dict, description="{name_zh, motto, ...}")
    today: dict = Field(default_factory=dict, description="{total, granted, rejected, spoof, no_face}")
    week: dict = Field(default_factory=dict)
    gates_online: int = 0
    gates_total: int = 0
    persons_total: int = 0
    persons_active: int = 0
    embedding_total: int = 0
    recent_logs: list[dict] = Field(default_factory=list, description="最近 10 条通行")
    by_decision_pie: list[dict] = Field(default_factory=list, description="ECharts 饼图: [{name, value}]")
    by_hour_line: list[dict] = Field(default_factory=list, description="ECharts 折线: [{hour, total}]，最近 24h")
    by_faculty_bar: list[dict] = Field(default_factory=list, description="按学部聚合通行数")
