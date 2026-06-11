"""ORM 冒烟测试 v2 (SWU 化)：验证模型定义、连通性、初始数据完整性。

只读校验已由 docs/schema.sql 注入的种子。所有断言对应 swu-context.md 内容。
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.store.models import (
    Admin, College, Faculty, Gate, Person, SystemConfig,
)


# ---------------------------------------------------------------------------
# 学部 / 学院
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_faculties_seeded(db) -> None:
    """11 学部 + 1 中外合作办学 = 12 行（swu-context §四）。"""
    n = await db.scalar(select(func.count(Faculty.id)))
    assert n == 12, f"expected 12 faculties, got {n}"


@pytest.mark.asyncio(loop_scope="session")
async def test_user_faculty_present(db) -> None:
    """用户所属"数学与信息科学学部"必须存在。"""
    f = await db.scalar(select(Faculty).where(Faculty.code == "faculty_math_info"))
    assert f is not None
    assert f.name == "数学与信息科学学部"


@pytest.mark.asyncio(loop_scope="session")
async def test_swu_cs_college_present(db) -> None:
    """计算机与信息科学学院·软件学院（学号 326 段）必须挂在数信学部下。"""
    c = await db.scalar(
        select(College)
        .options(selectinload(College.faculty))   # async 必须 eager-load 关系
        .where(College.code == "326"),
    )
    assert c is not None
    assert "计算机" in c.name
    assert c.faculty is not None
    assert c.faculty.code == "faculty_math_info"


@pytest.mark.asyncio(loop_scope="session")
async def test_colleges_count_reasonable(db) -> None:
    """学院数应在 40~60 区间（swu-context §四 列出 40+ 条目）。"""
    n = await db.scalar(select(func.count(College.id)))
    assert 40 <= n <= 60


# ---------------------------------------------------------------------------
# admins
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_default_admin_exists(db) -> None:
    """默认 superadmin 必须就绪（密码占位，由 P4 重写）。"""
    a = await db.scalar(select(Admin).where(Admin.username == "admin"))
    assert a is not None
    assert a.role == "superadmin"
    assert a.is_active is True
    assert a.email is None or "@" in a.email


# ---------------------------------------------------------------------------
# gates (北碚校区七门)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_seven_gates_seeded(db) -> None:
    """北碚校区七门（swu-context §三）必须就绪。"""
    n = await db.scalar(select(func.count(Gate.id)))
    assert n == 7, f"expected 7 SWU gates, got {n}"
    expected_codes = {
        "gate_hanhong", "gate_xuexing", "gate_tiansheng",
        "gate_xuefu", "gate_xueyuan", "gate_wenxing", "gate_jiangjun",
    }
    rows = await db.execute(select(Gate.code))
    actual = {r[0] for r in rows.all()}
    assert actual == expected_codes


@pytest.mark.asyncio(loop_scope="session")
async def test_main_two_gates_online(db) -> None:
    """含弘门 / 学行门作为首批接入点应至少处于 online。

    宽容断言：实际部署中管理员可改其它门为 online；不强求"恰好这两个"。
    """
    online = await db.execute(
        select(Gate.code).where(Gate.status == "online"),
    )
    online_codes = {r[0] for r in online.all()}
    assert {"gate_hanhong", "gate_xuexing"}.issubset(online_codes), \
        f"含弘门 + 学行门应至少在线，实际 online: {online_codes}"


# ---------------------------------------------------------------------------
# persons (demo 数据)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# system_configs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_system_configs_present(db) -> None:
    """关键 18 项系统配置必须齐全（含学校身份 + 识别参数 + UI 主题）。"""
    rows = await db.execute(select(SystemConfig.config_key))
    keys = {r[0] for r in rows.all()}
    expected = {
        # 学校身份
        "school.code", "school.name_zh", "school.name_en", "school.url",
        "school.icp", "school.motto", "school.spirit",
        "school.founded_year", "school.campus_main", "school.campus_main_addr",
        # 识别
        "recognition.match_threshold", "recognition.spoof_threshold",
        "recognition.anti_spoof_enabled", "recognition.embedder_model",
        "recognition.snapshot_keep_days",
        # UI
        "ui.theme.primary", "ui.theme.secondary", "ui.theme.gold",
    }
    assert expected.issubset(keys), f"missing: {expected - keys}"

    code = await db.scalar(
        select(SystemConfig.value_json).where(SystemConfig.config_key == "school.code"),
    )
    assert code == {"value": "10635"}, "school.code 应等于教育部 SWU 国标码"

    motto = await db.scalar(
        select(SystemConfig.value_json).where(SystemConfig.config_key == "school.motto"),
    )
    assert motto == {"value": "含弘光大，继往开来"}

    primary = await db.scalar(
        select(SystemConfig.value_json).where(SystemConfig.config_key == "ui.theme.primary"),
    )
    assert primary == {"value": "#003D7A"}, "西大蓝官方色"
