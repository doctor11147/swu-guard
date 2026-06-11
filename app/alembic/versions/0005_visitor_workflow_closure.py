"""0005 visitor workflow closure

- Link access_logs to visitor_appointments for visitor face-pass audit.
- Add indexes supporting visitor lookup and expiration jobs.
- Add DB-level slot range checks where supported by MySQL 8+.

Revision ID: 0005_visitor_workflow
Revises: 0004_visitor
Create Date: 2026-05-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_visitor_workflow"
down_revision: Union[str, None] = "0004_visitor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "access_logs",
        sa.Column(
            "visitor_appointment_id",
            sa.BigInteger(),
            nullable=True,
            comment="访客通行时关联的有效预约 id",
        ),
    )
    op.create_index(
        "ix_access_logs_visitor_appointment",
        "access_logs",
        ["visitor_appointment_id"],
    )
    op.create_foreign_key(
        "fk_access_logs_visitor_appointment",
        "access_logs",
        "visitor_appointments",
        ["visitor_appointment_id"],
        ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
    )

    op.create_index("ix_va_id_card", "visitor_appointments", ["id_card"])
    op.create_index(
        "ix_va_expire_scan",
        "visitor_appointments",
        ["status", "appointment_date", "departure_slot"],
    )
    op.create_index(
        "ix_va_valid_lookup",
        "visitor_appointments",
        ["person_id", "status", "appointment_date", "arrival_slot", "departure_slot"],
    )

    op.create_check_constraint(
        "ck_va_arrival_slot_range",
        "visitor_appointments",
        "arrival_slot BETWEEN 0 AND 5",
    )
    op.create_check_constraint(
        "ck_va_departure_slot_range",
        "visitor_appointments",
        "departure_slot BETWEEN 0 AND 5",
    )
    op.create_check_constraint(
        "ck_va_departure_after_arrival",
        "visitor_appointments",
        "departure_slot >= arrival_slot",
    )

    _seed_configs()


def downgrade() -> None:
    op.drop_constraint("ck_va_departure_after_arrival", "visitor_appointments", type_="check")
    op.drop_constraint("ck_va_departure_slot_range", "visitor_appointments", type_="check")
    op.drop_constraint("ck_va_arrival_slot_range", "visitor_appointments", type_="check")
    op.drop_index("ix_va_valid_lookup", table_name="visitor_appointments")
    op.drop_index("ix_va_expire_scan", table_name="visitor_appointments")
    op.drop_index("ix_va_id_card", table_name="visitor_appointments")
    op.drop_constraint("fk_access_logs_visitor_appointment", "access_logs", type_="foreignkey")
    op.drop_index("ix_access_logs_visitor_appointment", table_name="access_logs")
    op.drop_column("access_logs", "visitor_appointment_id")


def _seed_configs() -> None:
    configs = [
        ("visitor.workflow.required_face", '{"value": true}', "visitor appointment requires at least one enrolled face"),
        ("visitor.workflow.slot_labels", '{"value": ["00:00-04:00", "04:00-08:00", "08:00-12:00", "12:00-16:00", "16:00-20:00", "20:00-24:00"]}', "visitor daily appointment slots"),
    ]
    for key, val_json, desc in configs:
        op.execute(
            f"""INSERT INTO system_configs (config_key, value_json, description)
                VALUES ('{key}', CAST('{val_json}' AS JSON), '{desc}')
                ON DUPLICATE KEY UPDATE config_key=config_key"""
        )
