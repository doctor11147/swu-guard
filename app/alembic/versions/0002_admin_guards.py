"""0002 admin guards

- ``admins.role`` enum 加入 ``'guard'``
- 新增多对多表 ``admin_gate_permissions``（门卫 ↔ 所管辖门）

Revision ID: 0002_admin_guards
Revises: 0001_initial
Create Date: 2026-05-11

设计动机
--------
门卫 (guard) 是登录系统的管理员，但权限收敛到自己看护的门。
- 用 ``admins.role='guard'`` 标记
- 与门的关联放在独立的 join 表，避免 ``admins`` 表跟 ``gates`` 直接耦合
- superadmin / admin 不依赖该表（全权限）；该表仅对 guard 生效

幂等性
------
ALTER TABLE MODIFY COLUMN 加新 enum 值是无损操作；新建表使用 IF NOT EXISTS。
downgrade 严格反向。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_admin_guards"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) admins.role 加 'guard' enum 值
    op.execute(
        "ALTER TABLE `admins` "
        "MODIFY COLUMN `role` ENUM('superadmin','admin','guard','viewer') "
        "NOT NULL DEFAULT 'admin' COMMENT 'guard=门卫；仅看自己门相关数据'"
    )

    # 2) 多对多关联表
    op.create_table(
        "admin_gate_permissions",
        sa.Column("admin_id", sa.BigInteger().with_variant(
            sa.dialects.mysql.BIGINT(unsigned=True), "mysql"), nullable=False),
        sa.Column("gate_id", sa.BigInteger().with_variant(
            sa.dialects.mysql.BIGINT(unsigned=True), "mysql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False),
                  server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"],
                                name="fk_agp_admin", ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["gate_id"], ["gates.id"],
                                name="fk_agp_gate", ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("admin_id", "gate_id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_comment="门卫 ↔ 所管辖门（多对多）",
    )
    op.create_index("ix_agp_gate", "admin_gate_permissions", ["gate_id"])


def downgrade() -> None:
    op.drop_index("ix_agp_gate", table_name="admin_gate_permissions")
    op.drop_table("admin_gate_permissions")
    op.execute(
        "ALTER TABLE `admins` "
        "MODIFY COLUMN `role` ENUM('superadmin','admin','viewer') "
        "NOT NULL DEFAULT 'admin'"
    )
