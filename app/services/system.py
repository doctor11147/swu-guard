"""系统配置 / dashboard 业务逻辑。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.store.models import (
    AccessLog,
    College,
    FaceEmbedding,
    Faculty,
    Gate,
    Person,
    SystemConfig,
)


# ---------------------------------------------------------------------------
# 系统配置 KV
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    code = "CONFIG_ERROR"


class ConfigNotFound(ConfigError):
    code = "CONFIG_NOT_FOUND"


async def list_configs(db: AsyncSession) -> list[SystemConfig]:
    rows = await db.scalars(select(SystemConfig).order_by(SystemConfig.config_key))
    return list(rows.all())


async def get_config(db: AsyncSession, key: str) -> SystemConfig:
    cfg = await db.get(SystemConfig, key)
    if cfg is None:
        raise ConfigNotFound(f"config key={key!r} not found")
    return cfg


async def update_config(
    db: AsyncSession, key: str, value: Any, *, updated_by: int | None = None,
) -> SystemConfig:
    cfg = await get_config(db, key)
    cfg.value_json = {"value": value}
    cfg.updated_by = updated_by
    await db.commit()
    await db.refresh(cfg)
    return cfg


async def get_config_value(db: AsyncSession, key: str, default: Any = None) -> Any:
    """读取 ``value_json["value"]``。"""
    cfg = await db.get(SystemConfig, key)
    if cfg is None:
        return default
    return (cfg.value_json or {}).get("value", default)


# ---------------------------------------------------------------------------
# Faculty / College
# ---------------------------------------------------------------------------


async def list_faculties(db: AsyncSession) -> list[tuple[Faculty, int]]:
    """返回 [(Faculty, colleges_count), ...]。"""
    stmt = (
        select(Faculty, func.count(College.id))
        .outerjoin(College, College.faculty_id == Faculty.id)
        .group_by(Faculty.id)
        .order_by(Faculty.code)
    )
    rows = await db.execute(stmt)
    return [(f, int(c)) for f, c in rows.all()]


async def list_colleges(
    db: AsyncSession,
    *,
    faculty_id: int | None = None,
    active: bool | None = None,
    q: str | None = None,
) -> list[College]:
    stmt = select(College)
    if faculty_id is not None:
        stmt = stmt.where(College.faculty_id == faculty_id)
    if active is not None:
        stmt = stmt.where(College.is_active == active)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((College.name.like(like)) | (College.code.like(like)))
    stmt = stmt.order_by(College.code)
    rows = await db.scalars(stmt)
    return list(rows.all())


# ---------------------------------------------------------------------------
# Dashboard 聚合
# ---------------------------------------------------------------------------


def _today_local() -> datetime:
    """以 Asia/Shanghai 视角的"今日 00:00"（用 naive datetime，与 DB 一致）。"""
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


async def dashboard(
    db: AsyncSession,
    *,
    gate_scope: list[int] | None = None,
) -> dict:
    """聚合各类指标用于大屏。

    Args:
        gate_scope: 门卫视角下传入管辖 gate_id 列表；其他角色传 None 表示全集。
    """
    today_start = _today_local()
    week_start = today_start - timedelta(days=7)

    # 收敛门卫视角到管辖门
    def _scoped(stmt):
        if gate_scope is None:
            return stmt
        if not gate_scope:
            return stmt.where(AccessLog.id == -1)   # 空管辖 → 空结果
        return stmt.where(AccessLog.gate_id.in_(gate_scope))

    # 学校身份
    keys = ["school.name_zh", "school.motto", "school.spirit", "school.founded_year"]
    school_data: dict[str, Any] = {}
    for k in keys:
        school_data[k.replace("school.", "")] = await get_config_value(db, k)

    # 今日 / 7 日通行计数
    async def _decision_counts(since: datetime) -> dict:
        stmt = _scoped(
            select(AccessLog.decision, func.count(AccessLog.id))
            .where(AccessLog.ts >= since)
            .group_by(AccessLog.decision),
        )
        rows = await db.execute(stmt)
        out = {"granted": 0, "rejected": 0, "spoof": 0, "no_face": 0, "total": 0}
        for d, c in rows.all():
            out[d] = int(c)
            out["total"] += int(c)
        return out

    today = await _decision_counts(today_start)
    week = await _decision_counts(week_start)

    # 门禁统计：guard 只统计自己管辖的门
    gates_stmt = select(func.count(Gate.id))
    online_stmt = select(func.count(Gate.id)).where(Gate.status == "online")
    if gate_scope is not None:
        if not gate_scope:
            gates_stmt = gates_stmt.where(Gate.id == -1)
            online_stmt = online_stmt.where(Gate.id == -1)
        else:
            gates_stmt = gates_stmt.where(Gate.id.in_(gate_scope))
            online_stmt = online_stmt.where(Gate.id.in_(gate_scope))
    gates_total = int(await db.scalar(gates_stmt) or 0)
    gates_online = int(await db.scalar(online_stmt) or 0)

    # 人员统计
    persons_total = int(
        await db.scalar(
            select(func.count(Person.id)).where(Person.deleted_at.is_(None)),
        ) or 0,
    )
    persons_active = int(
        await db.scalar(
            select(func.count(Person.id)).where(
                and_(Person.deleted_at.is_(None), Person.status == "active"),
            ),
        ) or 0,
    )
    embedding_total = int(await db.scalar(select(func.count(FaceEmbedding.id))) or 0)

    # 最近 10 条
    recent_stmt = _scoped(
        select(AccessLog, Gate.name, Person.name, Person.external_id)
        .outerjoin(Gate, AccessLog.gate_id == Gate.id)
        .outerjoin(Person, AccessLog.matched_person_id == Person.id)
        .order_by(AccessLog.ts.desc())
        .limit(10),
    )
    recent_rows = await db.execute(recent_stmt)
    recent_logs = []
    for log, gate_name, person_name, ext_id in recent_rows.all():
        recent_logs.append({
            "id": log.id,
            "ts": log.ts.isoformat(),
            "decision": log.decision,
            "score": log.score,
            "spoof_score": log.spoof_score,
            "gate_name": gate_name,
            "person_name": person_name,
            "person_external_id": ext_id,
        })

    # 决策饼图（今日）
    by_decision_pie = [
        {"name": k, "value": today.get(k, 0)}
        for k in ("granted", "rejected", "spoof", "no_face")
    ]

    # 24h 折线（按小时）
    hour_since = datetime.now() - timedelta(hours=24)
    hour_stmt = _scoped(
        select(
            func.date_format(AccessLog.ts, "%Y-%m-%d %H:00").label("hour"),
            func.count(AccessLog.id),
        )
        .where(AccessLog.ts >= hour_since)
        .group_by("hour")
        .order_by("hour"),
    )
    hour_rows = await db.execute(hour_stmt)
    by_hour_line = [{"hour": h, "total": int(c)} for h, c in hour_rows.all()]

    # 学部柱状（今日）
    fac_stmt = _scoped(
        select(Faculty.name, func.count(AccessLog.id))
        .join(Person, AccessLog.matched_person_id == Person.id)
        .join(College, Person.college_id == College.id)
        .join(Faculty, College.faculty_id == Faculty.id)
        .where(AccessLog.ts >= today_start)
        .group_by(Faculty.id)
        .order_by(func.count(AccessLog.id).desc())
        .limit(10),
    )
    fac_rows = await db.execute(fac_stmt)
    by_faculty_bar = [{"faculty": n, "total": int(c)} for n, c in fac_rows.all()]

    return {
        "school": school_data,
        "today": today,
        "week": week,
        "gates_online": gates_online,
        "gates_total": gates_total,
        "persons_total": persons_total,
        "persons_active": persons_active,
        "embedding_total": embedding_total,
        "recent_logs": recent_logs,
        "by_decision_pie": by_decision_pie,
        "by_hour_line": by_hour_line,
        "by_faculty_bar": by_faculty_bar,
    }
