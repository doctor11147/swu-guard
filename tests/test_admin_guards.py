"""门卫 / 多对多关联表的 ORM 冒烟测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.store.models import Admin, admin_gate_permissions


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_role_enum_includes_guard(db) -> None:
    """admins.role 列在 0002 migration 后应能存 'guard' 值。"""
    from sqlalchemy import text
    row = await db.execute(
        text("SHOW COLUMNS FROM admins WHERE Field='role'"),
    )
    typedef = row.first()[1]
    assert "guard" in typedef, f"admins.role enum should contain 'guard': {typedef}"


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_gate_permissions_table_exists(db) -> None:
    """关联表存在且可读。"""
    from sqlalchemy import func
    count = await db.scalar(
        select(func.count()).select_from(admin_gate_permissions),
    )
    assert count is not None  # 表可读，初始 0 也 OK


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_gates_relationship_loads(db) -> None:
    """``Admin.gates`` relationship 可被 selectinload 安全加载（即便为空）。"""
    a = await db.scalar(
        select(Admin)
        .options(selectinload(Admin.gates))
        .where(Admin.username == "admin"),
    )
    assert a is not None
    # 默认 superadmin 不挂任何门（superadmin 不受该表约束）
    assert isinstance(a.gates, list)
