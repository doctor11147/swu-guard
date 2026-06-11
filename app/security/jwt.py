"""JWT 签发与校验 · HS256（python-jose）。

设计要点
--------
- 默认算法 HS256：密钥 32 字节，部署时 ``FACE_JWT_SECRET`` 环境变量注入。
  开发期回落到一个**显式带 "DEV-ONLY" 标记**的占位密钥；生产部署 lifespan
  会校验密钥是否被改过，未改则拒绝启动。
- access token 8h，refresh token 7d。可在 ``settings`` 重写。
- payload 字段（claim）：
    sub      : str  -> admin.id（字符串化以兼容 jose）
    username : str
    role     : str  -> 'superadmin' / 'admin' / 'viewer'
    type     : str  -> 'access' / 'refresh'（防止 refresh 冒充 access）
    iat / exp: int  -> Unix 秒
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt

ALGORITHM = "HS256"
ACCESS_TTL = timedelta(hours=8)
REFRESH_TTL = timedelta(days=7)

DEV_PLACEHOLDER_SECRET = (
    "DEV-ONLY-DO-NOT-USE-IN-PROD-please-export-FACE_JWT_SECRET-with-32-bytes"
)


class JWTConfigError(RuntimeError):
    """JWT 配置错误（如生产环境仍使用占位密钥）。"""


def _secret() -> str:
    return os.getenv("FACE_JWT_SECRET", DEV_PLACEHOLDER_SECRET)


def assert_production_secret() -> None:
    """生产模式启动校验：若仍是占位密钥则拒绝。

    应在 ``app/api/main.py`` lifespan 启动时调用，仅当
    ``FACE_ENV=production`` 时生效。
    """
    if os.getenv("FACE_ENV") == "production" and _secret() == DEV_PLACEHOLDER_SECRET:
        raise JWTConfigError(
            "FACE_JWT_SECRET 仍为开发占位值，禁止以此启动生产环境。"
            "请运行 `python -c 'import secrets; print(secrets.token_urlsafe(32))'` 生成密钥。"
        )


def create_token(
    *,
    subject: int,
    username: str,
    role: str,
    token_type: Literal["access", "refresh"] = "access",
    extra: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    """签发 token。返回 ``(token, expires_at_utc)``。"""
    now = datetime.now(tz=timezone.utc)
    ttl = ACCESS_TTL if token_type == "access" else REFRESH_TTL
    exp = now + ttl
    payload: dict[str, Any] = {
        "sub": str(subject),
        "username": username,
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, _secret(), algorithm=ALGORITHM)
    return token, exp


def decode_token(token: str, expected_type: Literal["access", "refresh"] = "access") -> dict[str, Any]:
    """校验 token 并返回 payload。

    抛出 ``JWTError`` 子类：
    - ``ExpiredSignatureError`` -> token 过期
    - 其他 ``JWTError``         -> 签名不合法 / type 不符
    """
    payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    if payload.get("type") != expected_type:
        raise JWTError(f"wrong token type: {payload.get('type')}, expected {expected_type}")
    return payload
