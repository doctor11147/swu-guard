"""通用 schema · 分页、错误、统一响应包装。"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """统一分页响应。"""

    items: list[T]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=200)


class ErrorOut(BaseModel):
    """统一错误响应。"""

    code: str
    message: str
    detail: dict | None = None


class OkOut(BaseModel):
    """简单确认响应。"""

    ok: bool = True
