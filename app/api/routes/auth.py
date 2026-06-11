"""认证路由 · /api/auth"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.auth import AdminOut, LoginIn, PasswordChangeIn, TokenOut
from app.schemas.common import OkOut
from app.services import auth as auth_svc
from app.services import guards as guards_svc

router = APIRouter(prefix="/auth", tags=["auth"])


async def _admin_to_out(db, admin) -> AdminOut:
    gate_ids = await guards_svc.list_admin_gate_ids(db, admin)
    return AdminOut(
        id=admin.id, username=admin.username, name=admin.name, email=admin.email,
        role=admin.role, is_active=admin.is_active,
        last_login_at=admin.last_login_at, created_at=admin.created_at,
        gate_ids=gate_ids,
    )


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: DbSession):
    try:
        admin = await auth_svc.authenticate(db, payload.username, payload.password)
    except auth_svc.InvalidCredentials as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": e.code, "message": str(e)},
        ) from None
    except auth_svc.InactiveAdmin as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": e.code, "message": str(e)},
        ) from None
    access, refresh, exp = auth_svc.issue_tokens(admin)
    return TokenOut(access_token=access, refresh_token=refresh,
                    expires_at=exp, user=await _admin_to_out(db, admin))


@router.get("/me", response_model=AdminOut)
async def me(db: DbSession, admin: CurrentAdmin):
    return await _admin_to_out(db, admin)


@router.put("/me/password", response_model=OkOut)
async def change_password(payload: PasswordChangeIn, db: DbSession, admin: CurrentAdmin):
    try:
        await auth_svc.change_password(db, admin, payload.old_password, payload.new_password)
    except auth_svc.WrongOldPassword as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": str(e)},
        ) from None
    return OkOut()


@router.post("/logout", response_model=OkOut)
async def logout(admin: CurrentAdmin):
    """无状态 JWT 不强制服务端撤销；前端清掉 token 即视为登出。"""
    return OkOut()
