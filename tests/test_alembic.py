"""Alembic 元链路测试。

- 当前库的 alembic_version 必须是 head（即 0001_initial）
- ORM 元数据与库 schema 不存在"实质性"差异（仅允许注释/索引名/FK 命名等
  非破坏性差异；这些通过排除某些 include_object 类型来过滤）
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from alembic.config import Config
from alembic.script import ScriptDirectory


@pytest.mark.asyncio(loop_scope="session")
async def test_alembic_version_is_head(db) -> None:
    """alembic_version 表里的版本号应是当前 head。"""
    cfg = Config("alembic.ini")
    head_rev = ScriptDirectory.from_config(cfg).get_current_head()
    assert head_rev is not None

    row = await db.execute(text("SELECT version_num FROM alembic_version"))
    db_rev = row.scalar()
    assert db_rev == head_rev, f"DB at {db_rev}, head is {head_rev}"
