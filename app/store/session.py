"""异步数据库会话工厂。

设计要点
--------
- 使用 SQLAlchemy 2.0 ``async_sessionmaker``，FastAPI 路由通过 ``Depends(get_db)``
  注入。
- 数据库 URL 必须通过环境变量 ``FACE_DB_URL`` 或 ``app/config.yaml`` 提供。
- ``echo=False`` 避免在生产中打印明文 SQL；调试时可临时改为 ``True``。

English summary
---------------
Async SQLAlchemy session factory. URL priority: env > config.yaml.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

def _resolve_db_url() -> str:
    """优先级：环境变量 > config.yaml；未配置时拒绝连接。"""
    if env := os.getenv("FACE_DB_URL"):
        return env
    try:
        from app.settings import Settings  # noqa: WPS433 - lazy import

        s = Settings.load()
        url = s.raw.get("database", {}).get("url")
        if url:
            return str(url)
    except Exception:
        pass
    raise RuntimeError("FACE_DB_URL is required; copy .env.example to .env and configure it")


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """全局唯一异步引擎。``lru_cache`` 保证单例。"""
    return create_async_engine(
        _resolve_db_url(),
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,    # MySQL wait_timeout 默认 8h，1h recycle 足够安全
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每请求一个 session。

    用法：
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)): ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def db_session() -> AsyncIterator[AsyncSession]:
    """脚本/CLI 用的上下文管理器版本（不走 FastAPI 依赖系统）。"""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
