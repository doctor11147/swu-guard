"""通行日志路由 · /api/access-logs"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, select

from app.api.deps import CurrentAdmin, DbSession, GateScope
from app.schemas.access_logs import AccessLogOut, AccessLogStatsOut
from app.schemas.common import Page
from app.store.models import AccessLog, Gate, Person

router = APIRouter(prefix="/access-logs", tags=["access_logs"])


def _build_filter(
    *,
    from_: datetime | None,
    to: datetime | None,
    decision: str | None,
    person_id: int | None,
    gate_id: int | None,
    gate_scope: list[int] | None = None,
):
    conds = []
    if from_:
        conds.append(AccessLog.ts >= from_)
    if to:
        conds.append(AccessLog.ts <= to)
    if decision:
        conds.append(AccessLog.decision == decision)
    if person_id is not None:
        conds.append(AccessLog.matched_person_id == person_id)
    if gate_id is not None:
        conds.append(AccessLog.gate_id == gate_id)
    # 门卫权限收敛：限定 gate_id 在管辖集合中
    if gate_scope is not None:
        if not gate_scope:
            # 管辖空 → 不返回任何日志
            conds.append(AccessLog.id == -1)
        else:
            conds.append(AccessLog.gate_id.in_(gate_scope))
    return and_(*conds) if conds else None


@router.get("", response_model=Page[AccessLogOut])
async def list_logs(
    db: DbSession,
    _admin: CurrentAdmin,
    scope: GateScope,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    decision: str | None = None,
    person_id: int | None = None,
    gate_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    filt = _build_filter(from_=from_, to=to, decision=decision,
                         person_id=person_id, gate_id=gate_id,
                         gate_scope=scope)

    base = select(AccessLog, Gate.name, Person.name, Person.external_id) \
        .outerjoin(Gate, AccessLog.gate_id == Gate.id) \
        .outerjoin(Person, AccessLog.matched_person_id == Person.id)
    if filt is not None:
        base = base.where(filt)

    count_stmt = select(func.count(AccessLog.id))
    if filt is not None:
        count_stmt = count_stmt.where(filt)
    total = int(await db.scalar(count_stmt) or 0)

    rows = await db.execute(
        base.order_by(AccessLog.ts.desc()).offset((page - 1) * page_size).limit(page_size),
    )
    items: list[AccessLogOut] = []
    for log, gate_name, person_name, ext_id in rows.all():
        out = AccessLogOut.model_validate(log)
        out.gate_name = gate_name
        out.person_name = person_name
        out.person_external_id = ext_id
        items.append(out)

    return Page[AccessLogOut](items=items, total=total, page=page, page_size=page_size)


@router.get("/stats", response_model=AccessLogStatsOut)
async def stats(db: DbSession, _admin: CurrentAdmin, scope: GateScope):
    """聚合统计；门卫视角下所有查询都限定到管辖门。"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # 复用的门卫收敛条件
    scope_cond = None
    if scope is not None:
        scope_cond = AccessLog.gate_id.in_(scope) if scope else (AccessLog.id == -1)

    def _scoped(stmt):
        return stmt.where(scope_cond) if scope_cond is not None else stmt

    by_decision_rows = await db.execute(
        _scoped(
            select(AccessLog.decision, func.count(AccessLog.id))
            .where(AccessLog.ts >= today_start)
            .group_by(AccessLog.decision),
        ),
    )
    by_decision = {"granted": 0, "rejected": 0, "spoof": 0, "no_face": 0}
    for d, c in by_decision_rows.all():
        by_decision[d] = int(c)

    by_day_rows = await db.execute(
        _scoped(
            select(
                func.date(AccessLog.ts).label("day"),
                AccessLog.decision,
                func.count(AccessLog.id),
            )
            .where(AccessLog.ts >= week_start)
            .group_by("day", AccessLog.decision)
            .order_by("day"),
        ),
    )
    by_day_dict: dict[str, dict] = {}
    for day, dec, c in by_day_rows.all():
        key = day.isoformat() if hasattr(day, "isoformat") else str(day)
        d = by_day_dict.setdefault(key, {"date": key, "total": 0, "granted": 0,
                                          "rejected": 0, "spoof": 0, "no_face": 0})
        d[dec] = int(c)
        d["total"] += int(c)

    by_hour_rows = await db.execute(
        _scoped(
            select(
                func.date_format(AccessLog.ts, "%Y-%m-%d %H:00").label("hour"),
                func.count(AccessLog.id),
            )
            .where(AccessLog.ts >= now - timedelta(hours=24))
            .group_by("hour")
            .order_by("hour"),
        ),
    )
    by_hour = [{"hour": h, "total": int(c)} for h, c in by_hour_rows.all()]

    by_gate_stmt = (
        select(Gate.id, Gate.name, func.count(AccessLog.id))
        .outerjoin(AccessLog, AccessLog.gate_id == Gate.id)
        .where(AccessLog.ts >= today_start)
        .group_by(Gate.id)
        .order_by(func.count(AccessLog.id).desc())
    )
    if scope is not None:
        by_gate_stmt = by_gate_stmt.where(Gate.id.in_(scope) if scope else (Gate.id == -1))
    by_gate_rows = await db.execute(by_gate_stmt)
    by_gate = [
        {"gate_id": gid, "gate_name": name, "total": int(c)}
        for gid, name, c in by_gate_rows.all()
    ]

    today_total = sum(by_decision.values())
    week_total = int(
        await db.scalar(
            _scoped(select(func.count(AccessLog.id)).where(AccessLog.ts >= week_start)),
        ) or 0,
    )

    return AccessLogStatsOut(
        by_day=list(by_day_dict.values()),
        by_hour=by_hour,
        by_gate=by_gate,
        by_decision=by_decision,
        today_total=today_total,
        week_total=week_total,
    )


@router.get("/{log_id}", response_model=AccessLogOut)
async def get_log(
    log_id: int, db: DbSession, _admin: CurrentAdmin, scope: GateScope,
):
    stmt = (
        select(AccessLog, Gate.name, Person.name, Person.external_id)
        .outerjoin(Gate, AccessLog.gate_id == Gate.id)
        .outerjoin(Person, AccessLog.matched_person_id == Person.id)
        .where(AccessLog.id == log_id)
    )
    if scope is not None:
        # 门卫只能看自己管辖门的日志
        if not scope:
            raise HTTPException(404, {"code": "LOG_NOT_FOUND", "message": "通行记录不存在"})
        stmt = stmt.where(AccessLog.gate_id.in_(scope))
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(404, {"code": "LOG_NOT_FOUND", "message": "通行记录不存在"})
    log, gate_name, person_name, ext_id = row
    out = AccessLogOut.model_validate(log)
    out.gate_name = gate_name
    out.person_name = person_name
    out.person_external_id = ext_id
    return out


@router.get("/export.csv")
async def export_csv(
    db: DbSession,
    _admin: CurrentAdmin,
    scope: GateScope,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    decision: str | None = None,
    person_id: int | None = None,
    gate_id: int | None = None,
    limit: int = Query(10000, ge=1, le=100000),
):
    filt = _build_filter(from_=from_, to=to, decision=decision,
                         person_id=person_id, gate_id=gate_id,
                         gate_scope=scope)
    stmt = select(AccessLog, Gate.name, Person.name, Person.external_id) \
        .outerjoin(Gate, AccessLog.gate_id == Gate.id) \
        .outerjoin(Person, AccessLog.matched_person_id == Person.id)
    if filt is not None:
        stmt = stmt.where(filt)
    stmt = stmt.order_by(AccessLog.ts.desc()).limit(limit)
    rows = await db.execute(stmt)

    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM, Excel 友好
    w = csv.writer(buf)
    w.writerow(["时间", "门禁", "学号/工号", "姓名", "决策", "相似度", "活体分", "备注"])
    for log, gate_name, person_name, ext_id in rows.all():
        w.writerow([
            log.ts.strftime("%Y-%m-%d %H:%M:%S"),
            gate_name or "",
            ext_id or "",
            person_name or "",
            log.decision,
            f"{log.score:.4f}" if log.score is not None else "",
            f"{log.spoof_score:.4f}" if log.spoof_score is not None else "",
            log.detail or "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="access_logs_{datetime.now():%Y%m%d_%H%M%S}.csv"',
        },
    )
