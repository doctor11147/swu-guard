"""访客预约 Pydantic v2 数据契约。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.persons import _validate_external_id

AppointmentStatus = Literal["pending", "approved", "rejected", "expired", "cancelled"]

# 每天 6 个时间段（每个 4 小时）
SLOT_LABELS: dict[int, str] = {
    0: "00:00-04:00", 1: "04:00-08:00", 2: "08:00-12:00",
    3: "12:00-16:00", 4: "16:00-20:00", 5: "20:00-24:00",
}


class AppointmentCreateIn(BaseModel):
    """访客提交预约请求。"""

    id_card: str = Field(..., min_length=18, max_length=18, description="18 位身份证号")
    visit_reason: str = Field(..., min_length=1, max_length=500)
    appointment_date: date | None = Field(None, description="兼容旧字段：到达日期")
    arrival_date: date | None = Field(None, description="到达日期")
    departure_date: date | None = Field(None, description="离开日期")
    arrival_slot: int = Field(..., ge=0, le=5, description="到达时间段 0-5")
    departure_slot: int = Field(..., ge=0, le=5, description="离开时间段 0-5")

    @field_validator("id_card")
    @classmethod
    def _normalize_id_card(cls, value: str) -> str:
        return _validate_external_id(value, "visitor")

    @model_validator(mode="after")
    def _check_window(self):
        if self.arrival_date is None:
            self.arrival_date = self.appointment_date
        if self.arrival_date is None:
            raise ValueError("请选择到达日期")
        if self.appointment_date is None:
            self.appointment_date = self.arrival_date
        if self.departure_date is None:
            self.departure_date = self.arrival_date
        start = (self.arrival_date, self.arrival_slot)
        end = (self.departure_date, self.departure_slot)
        if end < start:
            raise ValueError("离开时间不得早于到达时间")
        return self


class VisitorRegisterIn(BaseModel):
    """访客自助注册基本身份信息。人脸图通过单独 multipart 接口录入。"""

    id_card: str = Field(..., min_length=18, max_length=18, description="18 位身份证号")
    name: str = Field(..., min_length=1, max_length=128)
    phone: str | None = Field(None, max_length=32)
    email: str | None = Field(None, max_length=128)
    note: str | None = Field(None, max_length=500)

    @field_validator("id_card")
    @classmethod
    def _normalize_id_card(cls, value: str) -> str:
        return _validate_external_id(value, "visitor")


class VisitorRegisterOut(BaseModel):
    """访客自助注册响应。"""

    person_id: int
    id_card: str
    name: str
    status: str
    created: bool


class VisitorFaceRegisterOut(BaseModel):
    """访客自助人脸录入响应。"""

    person_id: int
    id_card: str
    added: int
    skipped_duplicates: int
    skipped_no_face: int
    skipped_spoof: int
    skipped_quality: int


class AppointmentLookupIn(BaseModel):
    """访客凭身份证号查询本人预约。"""

    id_card: str = Field(..., min_length=18, max_length=18)

    @field_validator("id_card")
    @classmethod
    def _normalize_id_card(cls, value: str) -> str:
        return _validate_external_id(value, "visitor")


class AppointmentCancelIn(BaseModel):
    """访客侧撤销预约。"""

    id_card: str = Field(..., min_length=18, max_length=18)

    @field_validator("id_card")
    @classmethod
    def _normalize_id_card(cls, value: str) -> str:
        return _validate_external_id(value, "visitor")


class AppointmentReviewIn(BaseModel):
    """审批请求。"""

    action: Literal["approve", "reject"]
    reason: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _check_reason(self):
        if self.action == "reject" and not (self.reason and self.reason.strip()):
            raise ValueError("拒绝预约必须填写理由")
        return self


class AppointmentOut(BaseModel):
    """预约记录响应。"""

    id: int
    person_id: int
    id_card: str
    visitor_name: str
    visit_reason: str
    arrival_slot: int
    departure_slot: int
    appointment_date: date
    arrival_date: date
    departure_date: date
    status: AppointmentStatus
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    reject_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TimeSlotInfo(BaseModel):
    """单个时间段信息。"""

    slot: int
    label: str
    booked: int
    max_capacity: int


class DailySlotsOut(BaseModel):
    """某日各时间段预约情况。"""

    date: date
    slots: list[TimeSlotInfo]
