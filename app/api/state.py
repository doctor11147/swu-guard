"""Process-wide singletons: pipeline, FAISS store, and write lock.

Kept in one place so route modules don't reach into each other for state.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from fastapi import Request

from app.core.pipeline import FacePipeline, build_default_pipeline
from app.settings import Settings
from app.store.faiss_index import FaissStore


@dataclass
class AppState:
    settings: Settings
    pipeline: FacePipeline
    faiss: FaissStore
    write_lock: threading.Lock   # serialise FAISS writes (file-based, not concurrent-safe)

    @classmethod
    def build(cls, settings: Settings) -> "AppState":
        pipeline = build_default_pipeline(settings)
        faiss_path = settings.data_dir / "faces.faiss"
        faiss = FaissStore(dim=pipeline.embedding_dim, index_path=faiss_path)
        return cls(
            settings=settings,
            pipeline=pipeline,
            faiss=faiss,
            write_lock=threading.Lock(),
        )


def get_app_state(request: Request) -> "AppState":
    """FastAPI 依赖：注入 lifespan 中构造的 AppState 单例。

    用法：
        async def handler(state: AppState = Depends(get_app_state)): ...
    """
    return request.app.state.app_state
