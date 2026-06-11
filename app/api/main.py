"""FastAPI 主入口（v0.2 · 全功能版）。

Run:
    conda activate face
    uvicorn app.api.main:app --host 0.0.0.0 --port 8000

挂载层级：
- /api/auth, /api/persons, /api/persons/{id}/faces, /api/recognize, /api/ws/recognize
  /api/access-logs, /api/gates, /api/system, /api/health, /api/version
- /                      (SPA 静态托管：先看 frontend/dist 再回落到 app/frontend)

启动期：
- 校验生产环境 JWT 密钥（FACE_ENV=production 时强制非占位）
- 加载推理 pipeline（含 SCRFD onnx, EdgeFace torch ckpt, MiniFAS torch ckpts）
- 打开 FAISS 索引（dim=512，文件持久化）
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# v0.2 新路由
from app.api.routes import (
    access_logs,
    adaptive,
    auth,
    faces,
    gates,
    health,
    metrics,
    persons,
    recognize,
    system,
    visitors,
)
from app.api.state import AppState
from app.security.jwt import assert_production_secret
from app.settings import Settings

logger = logging.getLogger(__name__)


async def _check_faiss_db_consistency(state: AppState) -> None:
    """Best-effort startup check: warn if FAISS and MySQL drift."""
    try:
        from sqlalchemy import func, select

        from app.store.models import FaceEmbedding
        from app.store.session import db_session

        async with db_session() as db:
            db_count = await db.scalar(select(func.count(FaceEmbedding.id))) or 0
        faiss_size = state.faiss.size
        if faiss_size != int(db_count):
            logger.warning(
                "FAISS/DB consistency mismatch: faiss.ntotal=%s face_embeddings=%s; "
                "startup continues, run app/scripts/rebuild_faiss_from_db.py if needed",
                faiss_size,
                int(db_count),
            )
        else:
            logger.info(
                "FAISS/DB consistency ok: faiss.ntotal=%s face_embeddings=%s",
                faiss_size,
                int(db_count),
            )
    except Exception as exc:
        logger.warning(
            "FAISS/DB consistency check skipped: %s: %s",
            type(exc).__name__,
            exc,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    assert_production_secret()
    settings = Settings.load()
    app.state.app_state = AppState.build(settings)
    await _check_faiss_db_consistency(app.state.app_state)
    try:
        from app.core.quality import get_quality_assessor

        await asyncio.to_thread(get_quality_assessor)
    except Exception:
        # 质量评估是低质量帧的安全加权，不应影响主服务启动。
        pass
    yield
    try:
        app.state.app_state.faiss.save()
    except Exception:
        pass


def create_app() -> FastAPI:
    settings = Settings.load()
    app = FastAPI(
        title="西南大学校园人脸识别门禁系统",
        version="0.2.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.get("cors_origins", ["*"]),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ----- /api/* (v0.2) -----
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(system.router, prefix="/api")
    app.include_router(persons.router, prefix="/api")
    app.include_router(faces.router, prefix="/api")        # /api/persons/{id}/faces
    app.include_router(gates.router, prefix="/api")
    app.include_router(access_logs.router, prefix="/api")
    app.include_router(recognize.router, prefix="/api")    # /api/recognize, /api/ws/recognize
    app.include_router(metrics.router, prefix="/api")      # /api/metrics
    app.include_router(adaptive.router, prefix="/api")    # /api/adaptive/*
    app.include_router(visitors.router, prefix="/api")   # /api/visitors/*

    # ----- 顶层 /health（与旧前端契约）-----
    @app.get("/health")
    def legacy_health():
        return {"status": "ok", "faiss_size": app.state.app_state.faiss.size}

    # ----- SPA 静态托管 -----
    # 优先用新前端 frontend/dist；不存在时回落 MVP 单页前端
    new_frontend = (Path(__file__).resolve().parents[2] / "frontend" / "dist")
    legacy_frontend = settings.frontend_dist
    chosen = new_frontend if new_frontend.exists() else legacy_frontend
    if chosen.exists():
        app.mount("/static", StaticFiles(directory=chosen), name="static")

        @app.get("/")
        def index():
            return FileResponse(chosen / "index.html")

    return app


app = create_app()
