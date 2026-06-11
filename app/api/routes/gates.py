"""门禁路由 · /api/gates"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentAdmin, DbSession, GateScope, OptionalGateScope, require_role
from app.schemas.common import OkOut
from app.schemas.gates import (
    GateCreateIn,
    GateOut,
    GateStatusUpdateIn,
    GateUpdateIn,
)
from app.store.models import AccessLog, Gate

router = APIRouter(prefix="/gates", tags=["gates"])


def _ensure_gate_in_scope(gate_id: int, scope: list[int] | None) -> None:
    """门卫仅能访问自己管辖的门；其它角色 scope=None 跳过。"""
    if scope is not None and gate_id not in scope:
        raise HTTPException(
            403, {"code": "GATE_NOT_IN_SCOPE", "message": "无权访问该门禁"},
        )


@router.get("", response_model=list[GateOut])
async def list_gates(
    db: DbSession,
    scope: OptionalGateScope,
    campus: str | None = None,
    status_: str | None = None,
    direction: str | None = None,
):
    stmt = select(Gate)
    if scope is not None:
        # guard 视角：只列自己管辖的门（空列表 → 空结果）
        if not scope:
            return []
        stmt = stmt.where(Gate.id.in_(scope))
    if campus:
        stmt = stmt.where(Gate.campus == campus)
    if status_:
        stmt = stmt.where(Gate.status == status_)
    if direction:
        stmt = stmt.where(Gate.direction == direction)
    stmt = stmt.order_by(Gate.code)
    rows = await db.scalars(stmt)
    return [GateOut.model_validate(g) for g in rows.all()]


@router.get("/{gate_id}", response_model=GateOut)
async def get_gate(
    gate_id: int, db: DbSession, scope: OptionalGateScope,
):
    _ensure_gate_in_scope(gate_id, scope)
    g = await db.get(Gate, gate_id)
    if g is None:
        raise HTTPException(404, {"code": "GATE_NOT_FOUND", "message": "门禁不存在"})
    return GateOut.model_validate(g)


@router.post(
    "",
    response_model=GateOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("superadmin", "admin"))],
)
async def create_gate(payload: GateCreateIn, db: DbSession):
    existing = await db.scalar(select(Gate).where(Gate.code == payload.code))
    if existing is not None:
        raise HTTPException(409, {"code": "GATE_DUPLICATE_CODE", "message": "门禁编码已存在"})
    g = Gate(**payload.model_dump())
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return GateOut.model_validate(g)


@router.put(
    "/{gate_id}",
    response_model=GateOut,
    dependencies=[Depends(require_role("superadmin", "admin"))],
)
async def update_gate(gate_id: int, payload: GateUpdateIn, db: DbSession):
    g = await db.get(Gate, gate_id)
    if g is None:
        raise HTTPException(404, {"code": "GATE_NOT_FOUND", "message": "门禁不存在"})
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(g, k, v)
    await db.commit()
    await db.refresh(g)
    return GateOut.model_validate(g)


@router.put("/{gate_id}/status", response_model=GateOut)
async def update_gate_status(
    gate_id: int,
    payload: GateStatusUpdateIn,
    db: DbSession,
    _admin: CurrentAdmin,
    scope: GateScope,
):
    """改门禁 status。门卫只能改自己管辖的门；admin/superadmin 不限。"""
    _ensure_gate_in_scope(gate_id, scope)
    g = await db.get(Gate, gate_id)
    if g is None:
        raise HTTPException(404, {"code": "GATE_NOT_FOUND", "message": "门禁不存在"})
    g.status = payload.status
    await db.commit()
    await db.refresh(g)
    return GateOut.model_validate(g)


@router.delete(
    "/{gate_id}",
    response_model=OkOut,
    dependencies=[Depends(require_role("superadmin"))],
)
async def delete_gate(gate_id: int, db: DbSession):
    g = await db.get(Gate, gate_id)
    if g is None:
        raise HTTPException(404, {"code": "GATE_NOT_FOUND", "message": "门禁不存在"})
    log_count = await db.scalar(
        select(func.count(AccessLog.id)).where(AccessLog.gate_id == gate_id),
    ) or 0
    if log_count > 0:
        raise HTTPException(
            409,
            {
                "code": "GATE_HAS_LOGS",
                "message": f"该门禁已有 {log_count} 条通行记录，不能物理删除；请改为 status=disabled",
            },
        )
    await db.delete(g)
    await db.commit()
    return OkOut()
