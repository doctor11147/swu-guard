"""Alembic env.py · 异步 + ORM 元数据接入。

设计要点
--------
- ``sqlalchemy.url`` 优先从环境变量 ``FACE_DB_URL`` 读取，未设时回落到
  ``alembic.ini``；这与 ``app/store/session.py`` 的解析顺序一致，确保
  生产部署时只需 export 一次环境变量。
- ``target_metadata`` 接入 ORM 模型，启用 ``alembic revision --autogenerate``。
- 确保仓库根目录在 sys.path 中，以便 ``from app.store.models import Base`` 成功。
"""
import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 确保 app.store.models 可导入（alembic 从仓库根运行）。
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.store.models import Base  # noqa: E402

config = context.config

# 优先级：环境变量 FACE_DB_URL > alembic.ini sqlalchemy.url
if env_url := os.getenv("FACE_DB_URL"):
    config.set_main_option("sqlalchemy.url", env_url)
else:
    raise RuntimeError("FACE_DB_URL is required for Alembic migrations")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
