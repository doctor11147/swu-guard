"""Security 单元测试 · 密码哈希 + JWT 签发与校验。"""
from __future__ import annotations

import time

import pytest
from jose import ExpiredSignatureError, JWTError

from app.security.jwt import (
    ACCESS_TTL,
    create_token,
    decode_token,
)
from app.security.password import hash_password, verify_password


# ---------------------------------------------------------------------------
# password
# ---------------------------------------------------------------------------


def test_password_hash_and_verify() -> None:
    h = hash_password("test-only-password")
    assert h.startswith("$2b$")
    assert verify_password("test-only-password", h) is True
    assert verify_password("wrong-password", h) is False


def test_password_verify_handles_garbage() -> None:
    """非法 hash 不应崩溃，应返回 False。"""
    assert verify_password("any", "not-a-bcrypt-hash") is False
    assert verify_password("any", "") is False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def test_jwt_roundtrip_access() -> None:
    token, exp = create_token(subject=42, username="admin", role="superadmin")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "42"
    assert payload["username"] == "admin"
    assert payload["role"] == "superadmin"
    assert payload["type"] == "access"
    # exp 应该约等于 now + ACCESS_TTL
    assert abs(payload["exp"] - (time.time() + ACCESS_TTL.total_seconds())) < 5


def test_jwt_refresh_token_type_check() -> None:
    """refresh token 不应被当作 access 通过。"""
    token, _ = create_token(subject=1, username="x", role="admin", token_type="refresh")
    with pytest.raises(JWTError):
        decode_token(token, expected_type="access")
    # 但用 refresh 类型解码应当通过
    payload = decode_token(token, expected_type="refresh")
    assert payload["type"] == "refresh"


def test_jwt_tampered_signature_rejected() -> None:
    """被篡改的 token 必须解码失败。"""
    token, _ = create_token(subject=1, username="x", role="admin")
    tampered = token[:-4] + "XXXX"
    with pytest.raises(JWTError):
        decode_token(tampered)


def test_jwt_expired_token_raises() -> None:
    """构造一个立即过期的 token，确认抛 ExpiredSignatureError。"""
    from datetime import datetime, timedelta, timezone

    from jose import jwt as _jwt

    from app.security.jwt import ALGORITHM, _secret

    past = datetime.now(tz=timezone.utc) - timedelta(seconds=10)
    payload = {
        "sub": "1", "username": "x", "role": "admin", "type": "access",
        "iat": int(past.timestamp()) - 1,
        "exp": int(past.timestamp()),
    }
    token = _jwt.encode(payload, _secret(), algorithm=ALGORITHM)
    with pytest.raises(ExpiredSignatureError):
        decode_token(token)
