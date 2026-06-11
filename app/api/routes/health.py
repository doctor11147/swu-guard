"""健康检查 / 版本路由 · /api/health, /api/version"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health(db: DbSession):
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "down"}


@router.get("/version")
async def version():
    return {
        "app": "face-gate",
        "version": "0.2.0",
        "edition": "swu",
    }
