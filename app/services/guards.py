"""门卫 (guard) 业务逻辑 · 管辖门关系与权限收敛。

设计要点
--------
- ``admin.role`` 是收敛 hook：只有 ``role='guard'`` 时管辖关系才生效，
  其余角色（superadmin / admin / viewer）忽略该表，按角色本身的权限走。
- ``list_admin_gate_ids`` 是核心 helper：路由层用它把查询条件过滤到自己门。
- 设置接口供 superadmin 后续维护门卫关系（写在 services 里保证业务层
  统一加锁/校验，路由层只调用）。
"""
from __future__ import annotations

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.store.models import Admin, Gate, admin_gate_permissions


async def list_admin_gate_ids(db: AsyncSession, admin: Admin) -> list[int]:
    """返回 admin 当前管辖的 gate.id 列表（仅 guard 角色非空）。"""
    if admin.role != "guard":
        return []
    rows = await db.scalars(
        select(admin_gate_permissions.c.gate_id)
        .where(admin_gate_permissions.c.admin_id == admin.id),
    )
    return [int(g) for g in rows.all()]


async def set_admin_gates(
    db: AsyncSession, admin_id: int, gate_ids: list[int],
) -> list[int]:
    """重置某门卫管辖的门集合（旧关系全清空，写入新集合）。"""
    admin = await db.get(Admin, admin_id)
    if admin is None:
        raise ValueError(f"admin id={admin_id} not found")
    await db.execute(
        delete(admin_gate_permissions)
        .where(admin_gate_permissions.c.admin_id == admin_id),
    )
    if gate_ids:
        await db.execute(
            insert(admin_gate_permissions),
            [{"admin_id": admin_id, "gate_id": gid} for gid in set(gate_ids)],
        )
    await db.commit()
    return await list_admin_gate_ids(db, admin)


async def get_or_create_guard(
    db: AsyncSession, *,
    username: str, password_hash: str, name: str, email: str | None,
) -> Admin:
    """幂等：按 username 找门卫账户，没有就创建（role=guard, is_active=True）。"""
    a = await db.scalar(select(Admin).where(Admin.username == username))
    if a is not None:
        return a
    a = Admin(
        username=username, password_hash=password_hash,
        name=name, email=email, role="guard", is_active=True,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


async def link_admin_to_gate_by_code(
    db: AsyncSession, admin: Admin, gate_code: str,
) -> bool:
    """把 admin 关联到 gate（按 code 找门）。已存在时幂等返回 False。"""
    gate = await db.scalar(select(Gate).where(Gate.code == gate_code))
    if gate is None:
        return False
    existing = await db.scalar(
        select(admin_gate_permissions.c.admin_id).where(
            admin_gate_permissions.c.admin_id == admin.id,
            admin_gate_permissions.c.gate_id == gate.id,
        ),
    )
    if existing is not None:
        return False
    await db.execute(
        insert(admin_gate_permissions).values(admin_id=admin.id, gate_id=gate.id),
    )
    await db.commit()
    return True
