"""0006 visitor cross-day appointments

Revision ID: 0006_visitor_cross_day
Revises: 0005_visitor_workflow
Create Date: 2026-05-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_visitor_cross_day"
down_revision: Union[str, None] = "0005_visitor_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.drop_constraint("ck_va_departure_after_arrival", "visitor_appointments", type_="check")
    except Exception:
        pass
    op.drop_index("ix_va_valid_lookup", table_name="visitor_appointments")
    op.drop_index("ix_va_expire_scan", table_name="visitor_appointments")

    op.add_column(
        "visitor_appointments",
        sa.Column("arrival_date", sa.Date(), nullable=True, comment="到达日期"),
    )
    op.add_column(
        "visitor_appointments",
        sa.Column("departure_date", sa.Date(), nullable=True, comment="离开日期"),
    )
    op.execute(
        "UPDATE visitor_appointments "
        "SET arrival_date = appointment_date, departure_date = appointment_date "
        "WHERE arrival_date IS NULL OR departure_date IS NULL"
    )
    op.alter_column(
        "visitor_appointments",
        "arrival_date",
        existing_type=sa.Date(),
        nullable=False,
        existing_comment="到达日期",
    )
    op.alter_column(
        "visitor_appointments",
        "departure_date",
        existing_type=sa.Date(),
        nullable=False,
        existing_comment="离开日期",
    )

    op.create_index(
        "ix_va_expire_scan",
        "visitor_appointments",
        ["status", "departure_date", "departure_slot"],
    )
    op.create_index(
        "ix_va_valid_lookup",
        "visitor_appointments",
        ["person_id", "status", "arrival_date", "departure_date", "arrival_slot", "departure_slot"],
    )
    op.create_index(
        "ix_va_window",
        "visitor_appointments",
        ["person_id", "arrival_date", "departure_date", "status"],
    )
    op.create_check_constraint(
        "ck_va_departure_after_arrival",
        "visitor_appointments",
        "(departure_date > arrival_date) OR "
        "(departure_date = arrival_date AND departure_slot >= arrival_slot)",
    )


def downgrade() -> None:
    try:
        op.drop_constraint("ck_va_departure_after_arrival", "visitor_appointments", type_="check")
    except Exception:
        pass
    op.drop_index("ix_va_window", table_name="visitor_appointments")
    op.drop_index("ix_va_valid_lookup", table_name="visitor_appointments")
    op.drop_index("ix_va_expire_scan", table_name="visitor_appointments")

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
        "ck_va_departure_after_arrival",
        "visitor_appointments",
        "departure_slot >= arrival_slot",
    )
    op.drop_column("visitor_appointments", "departure_date")
    op.drop_column("visitor_appointments", "arrival_date")
