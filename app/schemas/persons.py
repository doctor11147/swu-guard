"""人员 / 学部 / 学院 相关 schema。

学号校验规则（西南大学，swu-context.md §五）：
- 本科生（role='student'）: 严格 15 位数字。前两位 22 表示本科生类型。
- 研究生（role='graduate'）: 通常 13-15 位，宽松校验
- 教师 / 职工: 工号 5-10 位
- 访客: 任意长度
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

PersonRole = Literal["student", "graduate", "teacher", "staff", "visitor"]
PersonStatus = Literal["active", "suspended", "graduated", "expired"]
Campus = Literal["beibei", "rongchang"]
DormZone = Literal["nan", "zhu", "mei", "li", "ju", "tao", "xing"]


# ---------------------------------------------------------------------------
# Faculty / College
# ---------------------------------------------------------------------------


class FacultyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    is_active: bool


class FacultyDetailOut(FacultyOut):
    colleges_count: int = 0


class CollegeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    faculty_id: int | None
    code: str
    name: str
    short_name: str | None
    is_active: bool


class CollegeCreateIn(BaseModel):
    faculty_id: int | None = None
    code: str = Field(..., min_length=1, max_length=16)
    name: str = Field(..., min_length=1, max_length=128)
    short_name: str | None = Field(None, max_length=32)


class CollegeUpdateIn(BaseModel):
    faculty_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=128)
    short_name: str | None = Field(None, max_length=32)
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------


_SWU_UG_PATTERN = re.compile(r"^22\d{13}$")  # 本科生 15 位，前两位 22
# 访客身份证号：17 位数字 + 最后 1 位为数字或 X/x（GB 11643 形态，不验校验码）
_ID_CARD_PATTERN = re.compile(r"^\d{17}[\dXx]$")


def _validate_external_id(external_id: str, role: str) -> str:
    if role == "student":
        if not _SWU_UG_PATTERN.match(external_id):
            raise ValueError(
                "本科生学号必须为 15 位数字且以 22 开头（西南大学约定），"
                f"如 222022326062999，收到 {external_id!r}",
            )
        year = int(external_id[2:6])
        if not (2000 <= year <= 2030):
            raise ValueError(f"学号中入学年份 {year} 超出合理范围 [2000, 2030]")
    elif role == "graduate":
        if not (10 <= len(external_id) <= 15) or not external_id.isdigit():
            raise ValueError("研究生学号长度 10-15 位数字")
    elif role in ("teacher", "staff"):
        if not (5 <= len(external_id) <= 10):
            raise ValueError("教师/职工工号长度 5-10")
    elif role == "visitor":
        # 访客以二代身份证号为准（不校验 GB 11643 校验码，仅按形态约束）。
        if not _ID_CARD_PATTERN.match(external_id):
            raise ValueError(
                "访客需提供 18 位二代身份证号：前 17 位数字，末位数字或 X",
            )
        return external_id.upper()   # 末尾 X 统一大写存储
    return external_id


class PersonCreateIn(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=128)
    role: PersonRole = "student"
    college_id: int | None = None
    major: str | None = Field(None, max_length=128)
    class_code: str | None = Field(None, max_length=64)
    enrollment_year: int | None = Field(None, ge=1900, le=2100)
    campus: Campus = "beibei"
    dorm_zone: DormZone | None = None
    phone: str | None = Field(None, max_length=32)
    email: str | None = Field(None, max_length=128)
    note: str | None = None

    @model_validator(mode="after")
    def _check_external_id(self):
        _validate_external_id(self.external_id, self.role)
        return self


class PersonUpdateIn(BaseModel):
    """更新允许部分字段；不可修改 external_id（学号是身份）。"""

    name: str | None = Field(None, min_length=1, max_length=128)
    role: PersonRole | None = None
    college_id: int | None = None
    major: str | None = Field(None, max_length=128)
    class_code: str | None = Field(None, max_length=64)
    enrollment_year: int | None = Field(None, ge=1900, le=2100)
    campus: Campus | None = None
    dorm_zone: DormZone | None = None
    phone: str | None = Field(None, max_length=32)
    email: str | None = Field(None, max_length=128)
    status: PersonStatus | None = None
    note: str | None = None


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    name: str
    role: PersonRole
    college_id: int | None
    faculty_name: str | None
    school_name: str | None
    major: str | None
    class_code: str | None
    enrollment_year: int | None
    campus: Campus
    dorm_zone: DormZone | None
    phone: str | None
    email: str | None
    status: PersonStatus
    note: str | None
    created_at: datetime
    updated_at: datetime
    embedding_count: int = 0


class PersonDetailOut(PersonOut):
    """详情视图含最近通行 5 条。"""

    college_name: str | None = None
    faculty_id: int | None = None


# ---------------------------------------------------------------------------
# Person 学号解析（前端 helper）
# ---------------------------------------------------------------------------


class StudentIdParseOut(BaseModel):
    """解析 SWU 15 位本科生学号。"""

    valid: bool
    type_code: Optional[str] = None
    type_name: Optional[str] = None
    enrollment_year: Optional[int] = None
    college_code: Optional[str] = None
    class_no: Optional[str] = None
    seq_no: Optional[str] = None

    @classmethod
    def parse(cls, sid: str) -> "StudentIdParseOut":
        if len(sid) != 15 or not sid.isdigit():
            return cls(valid=False)
        type_code = sid[0:2]
        type_name = {
            "22": "本科生", "21": "硕士研究生", "20": "博士研究生", "25": "留学生",
        }.get(type_code, "未知")
        try:
            year = int(sid[2:6])
        except ValueError:
            return cls(valid=False)
        return cls(
            valid=True,
            type_code=type_code,
            type_name=type_name,
            enrollment_year=year,
            college_code=sid[6:9],
            class_no=sid[9:12],
            seq_no=sid[12:15],
        )
