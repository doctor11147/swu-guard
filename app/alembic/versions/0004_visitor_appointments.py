"""0004 visitor appointments

- 新增 ``visitor_appointments`` 表（访客预约 + 审批 + 时间窗口）
- ``system_configs`` 写入预约相关默认配置

业务流：
  访客注册（persons, role='visitor'）→ 提交预约（身份证号 + 来访原因 + 时间段）
  → 门卫/管理员审批 → 通过后在时间段内可刷脸入校 → 过期自动失效

Revision ID: 0004_visitor
Revises: 0003_adaptive
Create Date: 2026-05-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "0004_visitor"
down_revision: Union[str, None] = "0003_adaptive"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 每天 6 个时间段，每个 4 小时
SLOT_LABELS = [
    "00:00-04:00", "04:00-08:00", "08:00-12:00",
    "12:00-16:00", "16:00-20:00", "20:00-24:00",
]


def upgrade() -> None:
    op.create_table(
        "visitor_appointments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "person_id", mysql.BIGINT(unsigned=True), nullable=False,
            comment="FK persons.id（该人员 role 应为 'visitor'）",
        ),
        sa.Column(
            "id_card", sa.String(32), nullable=False,
            comment="冗余：访客身份证号（与 persons.external_id 一致），方便查询",
        ),
        sa.Column("visitor_name", sa.String(128), nullable=False, comment="冗余：访客姓名"),
        sa.Column(
            "visit_reason", sa.String(512), nullable=False,
            comment="来访原因",
        ),
        sa.Column(
            "arrival_slot", sa.SmallInteger(), nullable=False,
            comment="到达时间段 (0-5)：0=00-04, 1=04-08, 2=08-12, 3=12-16, 4=16-20, 5=20-24",
        ),
        sa.Column(
            "departure_slot", sa.SmallInteger(), nullable=False,
            comment="离开时间段 (0-5)，应 >= arrival_slot",
        ),
        sa.Column(
            "appointment_date", sa.Date(), nullable=False,
            comment="预约日期",
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", "expired", "cancelled",
                   name="appointment_status"),
            nullable=False, server_default="pending",
            comment="pending=待审批 / approved=已通过 / rejected=已拒绝 / expired=已过期 / cancelled=已取消",
        ),
        sa.Column(
            "reviewed_by", mysql.BIGINT(unsigned=True), nullable=True,
            comment="审批人 admins.id",
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "reject_reason", sa.String(512), nullable=True,
            comment="拒绝理由",
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["person_id"], ["persons.id"],
            name="fk_appointment_person", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["admins.id"],
            name="fk_appointment_reviewer", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_default_charset="utf8mb4",
        mysql_comment="访客预约记录",
    )
    op.create_index("ix_va_person_date", "visitor_appointments", ["person_id", "appointment_date"])
    op.create_index("ix_va_status", "visitor_appointments", ["status"])
    op.create_index("ix_va_date_status", "visitor_appointments", ["appointment_date", "status"])

    # 种子配置
    _seed_configs()


def downgrade() -> None:
    op.drop_index("ix_va_date_status", table_name="visitor_appointments")
    op.drop_index("ix_va_status", table_name="visitor_appointments")
    op.drop_index("ix_va_person_date", table_name="visitor_appointments")
    op.drop_table("visitor_appointments")
    op.execute("DROP TYPE IF EXISTS appointment_status")


def _seed_configs() -> None:
    configs = [
        ("visitor.slot_count",      '{"value": 6}'),
        ("visitor.slot_duration_h", '{"value": 4}'),
        ("visitor.max_per_slot",    '{"value": 20}'),
        ("visitor.auto_expire_min", '{"value": 30}'),
    ]
    for key, val_json in configs:
        op.execute(
            f"""INSERT INTO system_configs (config_key, value_json, description)
                VALUES ('{key}', CAST('{val_json}' AS JSON), 'visitor appointment')
                ON DUPLICATE KEY UPDATE config_key=config_key"""
        )
