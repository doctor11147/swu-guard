"""Recent recognition statistics — read-only aggregations on access_logs.

English summary
---------------
Queries the trailing N-minute window from access_logs and returns
reject / low-quality / spoof rates plus average similarity.
A low sample count is returned as-is — the orchestrator may down-weight.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.adaptive import RecentRecognitionStats
from app.store.models import AccessLog


async def get_recent_stats(
    db: AsyncSession,
    *,
    window_minutes: int = 15,
) -> RecentRecognitionStats:
    """Aggregate recognition stats over the last `window_minutes` minutes.

    If access_logs is empty or the window yields zero events, the returned
    object has all fields set to 0 / None (safe for orchestrator fallback).
    """
    since = datetime.now() - timedelta(minutes=window_minutes)

    base_q = select(
        func.count(AccessLog.id).label("total"),
        func.avg(AccessLog.score).label("avg_sim"),
        func.sum(
            case((AccessLog.decision == "rejected", 1), else_=0)
        ).label("n_reject"),
        func.sum(
            case((AccessLog.decision == "spoof", 1), else_=0)
        ).label("n_spoof"),
    ).where(AccessLog.ts >= since)

    row = (await db.execute(base_q)).one_or_none()
    if row is None or row.total == 0:
        return RecentRecognitionStats(
            window_minutes=window_minutes,
            total_events=0,
            reject_rate=0.0,
            low_quality_rate=0.0,
            spoof_reject_rate=0.0,
            avg_similarity=None,
        )

    total = int(row.total)
    return RecentRecognitionStats(
        window_minutes=window_minutes,
        total_events=total,
        reject_rate=int(row.n_reject or 0) / total,
        low_quality_rate=0.0,       # 暂无 quality gate 字段，占位
        spoof_reject_rate=int(row.n_spoof or 0) / total,
        avg_similarity=float(row.avg_sim) if row.avg_sim is not None else None,
    )
