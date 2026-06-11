"""0001 initial baseline

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-10

本 migration 是一个**显式空 baseline**。

设计原因
--------
首次部署使用 ``scripts/schema.sql`` 直接导入MySQL。Alembic autogenerate
在已就位的库上只能检测到注释、索引命名、
FK 命名等无副作用的表面差异，生成的脚本若执行反而会报错（drop 不存在的 FK）。

正确做法：
1. 提交本空 migration 作为版本 0001；
2. 在已存在 schema 的环境运行 ``alembic stamp 0001_initial`` 标记当前库为此版本；
3. **在干净库上从零部署**则改用 ``alembic upgrade head``，配合后续会新增的
   migrations 即可重建（届时如需，可在新 migration 中 ``op.execute(open(schema.sql).read())``
   或纯 ORM ``op.create_table`` 重写）；
4. 后续任何 ORM 模型变更，都通过 ``alembic revision --autogenerate`` 在本
   baseline 之上累加。

English summary
---------------
Empty baseline. The initial schema is loaded from docs/schema.sql; this
migration just marks "the database is at version 0001". All subsequent ORM
changes will autogenerate proper deltas on top.
"""
from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op: schema is bootstrapped by docs/schema.sql."""


def downgrade() -> None:
    """No-op: nothing to undo for the baseline."""
