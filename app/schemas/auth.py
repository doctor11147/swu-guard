"""认证相关 schema。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class AdminOut(BaseModel):
    id: int
    username: str
    name: str
    email: str | None
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    # 当 role='guard' 时，列出此账户管辖的 gate.id；其它角色为空列表（全权限）。
    gate_ids: list[int] = []


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: AdminOut


class PasswordChangeIn(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
