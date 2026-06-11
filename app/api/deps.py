"""FastAPI 依赖注入工厂 · DB session / JWT auth / 角色守卫。

用法：
    @router.get("/me")
    async def me(admin: Admin = Depends(get_current_admin)):
        return admin

    @router.delete("/persons/{id}", dependencies=[Depends(require_role("superadmin"))])
    async def delete(...):
        ...
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jose import ExpiredSignatureError, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.security.jwt import decode_token
from app.store.models import Admin
from app.store.session import get_db

# tokenUrl 指向登录路由；/api 前缀在 main.py 的 include_router 中加上。
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_admin(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> Admin:
    """从 JWT 还原当前管理员。token 失效/被禁用一律 401。"""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "AUTH_INVALID_CREDENTIALS", "message": "无效或过期的凭证"},
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token, expected_type="access")
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_TOKEN_EXPIRED", "message": "token 已过期"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except JWTError:
        raise credentials_exc from None

    sub = payload.get("sub")
    if sub is None:
        raise credentials_exc

    admin = await db.get(Admin, int(sub))
    if admin is None or not admin.is_active:
        raise credentials_exc
    return admin


CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]


def require_role(*roles: str):
    """工厂：返回一个依赖，只有 admin.role 在 ``roles`` 中才放行。"""

    async def _checker(admin: CurrentAdmin) -> Admin:
        if admin.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "AUTH_FORBIDDEN", "message": f"需要角色: {roles}"},
            )
        return admin

    return _checker


# 仅"管理员级"角色（superadmin / admin）可访问
forbid_guard = require_role("superadmin", "admin")


async def gate_scope(
    admin: CurrentAdmin, db: DbSession,
) -> list[int] | None:
    """权限收敛 helper。

    Returns:
        - ``None``：管理员级（superadmin/admin/viewer），无门禁限制
        - ``list[int]``：门卫，只能看这些 gate_id；空列表代表"管不到任何门"
    """
    if admin.role != "guard":
        return None
    # 局部导入避免与 services 循环依赖
    from app.services.guards import list_admin_gate_ids
    return await list_admin_gate_ids(db, admin)


GateScope = Annotated[list[int] | None, Depends(gate_scope)]


async def get_optional_current_admin(request: Request, db: DbSession) -> Admin | None:
    """Best-effort JWT auth for public read endpoints.

    No Authorization header means anonymous access. Invalid or expired tokens
    still fail as 401 so callers do not unknowingly operate with a bad session.
    """
    authorization = request.headers.get("Authorization")
    scheme, token = get_authorization_scheme_param(authorization)
    if not authorization or scheme.lower() != "bearer":
        return None
    return await get_current_admin(token, db)


OptionalCurrentAdmin = Annotated[Admin | None, Depends(get_optional_current_admin)]


async def optional_gate_scope(
    admin: OptionalCurrentAdmin,
    db: DbSession,
) -> list[int] | None:
    """Gate scope for public reads: anonymous and admin-level users see all."""
    if admin is None or admin.role != "guard":
        return None
    from app.services.guards import list_admin_gate_ids
    return await list_admin_gate_ids(db, admin)


OptionalGateScope = Annotated[list[int] | None, Depends(optional_gate_scope)]
