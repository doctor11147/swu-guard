"""认证业务逻辑：登录、刷新、修改密码。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.jwt import create_token
from app.security.password import hash_password, verify_password
from app.store.models import Admin


class AuthError(Exception):
    code: str = "AUTH_ERROR"


class InvalidCredentials(AuthError):
    code = "AUTH_INVALID_CREDENTIALS"


class InactiveAdmin(AuthError):
    code = "AUTH_INACTIVE"


class WrongOldPassword(AuthError):
    code = "AUTH_WRONG_OLD_PASSWORD"


async def authenticate(db: AsyncSession, username: str, password: str) -> Admin:
    """登录校验：用户名+密码 -> Admin 或抛异常。"""
    admin = await db.scalar(select(Admin).where(Admin.username == username))
    if admin is None or not verify_password(password, admin.password_hash):
        raise InvalidCredentials("用户名或密码错误")
    if not admin.is_active:
        raise InactiveAdmin("账户已禁用")
    admin.last_login_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    await db.commit()
    return admin


def issue_tokens(admin: Admin) -> tuple[str, str, datetime]:
    """签发 access + refresh token，返回 ``(access, refresh, access_exp)``。"""
    access, exp = create_token(
        subject=admin.id, username=admin.username, role=admin.role, token_type="access",
    )
    refresh, _ = create_token(
        subject=admin.id, username=admin.username, role=admin.role, token_type="refresh",
    )
    return access, refresh, exp


async def change_password(
    db: AsyncSession, admin: Admin, old_password: str, new_password: str,
) -> None:
    if not verify_password(old_password, admin.password_hash):
        raise WrongOldPassword("旧密码不正确")
    admin.password_hash = hash_password(new_password)
    await db.commit()
