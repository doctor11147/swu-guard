"""FastAPI 实例工厂（管理后台子集，不含 recognize/pipeline）。

P6 完成后由 ``app/api/main.py`` 在此基础上额外挂载 recognize / WebSocket 路由
（需要懒加载推理 pipeline）；本工厂仅挂载纯 CRUD 类路由，可用于：
- pytest 集成测试（避免加载 ONNX 模型）
- 仅管理面板的轻量部署
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import access_logs, adaptive, auth, gates, health, persons, system, visitors
from app.settings import Settings
from app.store.faiss_index import FaissStore


@dataclass
class AdminAppState:
    """Admin 面板专用的轻量 state（不含推理 pipeline）。

    与 ``app/api/state.py`` 的 ``AppState`` 字段名保持一致，所以
    ``api/state.py:get_app_state`` 依赖能在两种 app 上工作：
    - 测试 / 仅管理部署：注入此最小实例
    - 完整部署（P6）：注入含 pipeline 的 ``AppState``
    """

    faiss: FaissStore
    write_lock: threading.Lock


def _build_admin_state(embedding_dim: int = 512) -> AdminAppState:
    settings = Settings.load()
    faiss_path = settings.data_dir / "faces.faiss"
    return AdminAppState(
        faiss=FaissStore(dim=embedding_dim, index_path=faiss_path),
        write_lock=threading.Lock(),
    )


@asynccontextmanager
async def _admin_lifespan(app: FastAPI):
    app.state.app_state = _build_admin_state()
    yield


def create_admin_app() -> FastAPI:
    """构造仅管理面板（无推理）的 FastAPI 实例。"""
    app = FastAPI(
        title="西南大学校园人脸识别门禁系统 · Admin API",
        version="0.2.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=_admin_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # 开发期；生产由 settings 收紧
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # /api 前缀统一在此处注入
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(system.router, prefix="/api")
    app.include_router(persons.router, prefix="/api")
    app.include_router(gates.router, prefix="/api")
    app.include_router(access_logs.router, prefix="/api")
    app.include_router(adaptive.router, prefix="/api")
    app.include_router(visitors.router, prefix="/api")

    return app
