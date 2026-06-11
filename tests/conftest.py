"""pytest 共享 fixtures。

- 自动启用 ``asyncio_mode=auto`` + ``asyncio_default_fixture_loop_scope=session``
  （详见根 pytest.ini）
- 引擎在 session 范围创建一次并复用，避免与 ``lru_cache`` 单例的事件循环冲突
- 默认数据库走本机 face_gate（P1 已初始化）
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.store.session import _resolve_db_url


from sqlalchemy.pool import NullPool


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    """全测试会话共享一个 async engine。

    ``loop_scope="session"`` 强制 engine 与所有依赖它的测试共享同一个 event loop，
    否则 asyncmy 在 teardown 时尝试关闭连接会撞上已关闭的 loop。
    使用 ``NullPool`` 简化连接生命周期。
    """
    e = create_async_engine(_resolve_db_url(), poolclass=NullPool)
    yield e
    await e.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """每个测试函数一个新 session（仍用 session loop）。"""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session
        await session.close()
