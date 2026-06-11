"""门禁相关 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GateCampus = Literal["beibei", "rongchang"]
GateDirection = Literal["in", "out", "both"]
GateStatus = Literal["online", "offline", "disabled"]


class GateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    campus: GateCampus
    location: str | None
    direction: GateDirection
    ip_address: str | None
    status: GateStatus
    note: str | None
    created_at: datetime
    updated_at: datetime


class GateCreateIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=128)
    campus: GateCampus = "beibei"
    location: str | None = Field(None, max_length=255)
    direction: GateDirection = "both"
    ip_address: str | None = Field(None, max_length=64)
    status: GateStatus = "offline"
    note: str | None = None


class GateUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    campus: GateCampus | None = None
    location: str | None = Field(None, max_length=255)
    direction: GateDirection | None = None
    ip_address: str | None = Field(None, max_length=64)
    status: GateStatus | None = None
    note: str | None = None


class GateStatusUpdateIn(BaseModel):
    status: GateStatus
