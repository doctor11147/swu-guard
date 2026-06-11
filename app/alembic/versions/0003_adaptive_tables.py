"""0003 adaptive control tables

- 新增 ``environment_snapshots``（环境感知快照）
- 新增 ``adaptive_policy_logs``（策略审计日志）
- ``access_logs`` 增加 3 个自适应字段
- ``system_configs`` 写入自适应默认配置

Revision ID: 0003_adaptive
Revises: 0002_admin_guards
Create Date: 2026-05-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "0003_adaptive"
down_revision: Union[str, None] = "0002_admin_guards"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── environment_snapshots ──────────────────────────────────────
    op.create_table(
        "environment_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("gate_id", sa.BigInteger(), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, comment="vlm/deepseek/mock/rule/open_meteo"),
        sa.Column("location_name", sa.String(128), nullable=True),
        sa.Column("scene_tag", sa.String(64), nullable=True, comment="outdoor/semi_outdoor/indoor/backlight/night/rain_fog/unknown"),
        sa.Column("lighting_quality", sa.String(32), nullable=True, comment="good/overcast/low_light/backlight/unstable/unsafe"),
        sa.Column("weather_text", sa.String(128), nullable=True),
        sa.Column("cloud_pct", sa.Float(), nullable=True),
        sa.Column("visibility_km", sa.Float(), nullable=True),
        sa.Column("precipitation_mm", sa.Float(), nullable=True),
        sa.Column("irradiance", sa.Float(), nullable=True),
        sa.Column("humidity_pct", sa.Float(), nullable=True),
        sa.Column("is_day", sa.Boolean(), nullable=True),
        sa.Column("camera_luma_mean", sa.Float(), nullable=True),
        sa.Column("camera_luma_std", sa.Float(), nullable=True),
        sa.Column("camera_blur_score", sa.Float(), nullable=True),
        sa.Column("under_exposed_ratio", sa.Float(), nullable=True),
        sa.Column("over_exposed_ratio", sa.Float(), nullable=True),
        sa.Column("recent_reject_rate", sa.Float(), nullable=True),
        sa.Column("recent_low_quality_rate", sa.Float(), nullable=True),
        sa.Column("recent_spoof_reject_rate", sa.Float(), nullable=True),
        sa.Column("recent_avg_similarity", sa.Float(), nullable=True),
        sa.Column("vlm_raw_json", sa.JSON(), nullable=True),
        sa.Column("weather_raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_default_charset="utf8mb4",
        mysql_comment="环境感知快照",
    )
    op.create_index("ix_env_gate_time", "environment_snapshots", ["gate_id", "created_at"])
    op.create_index("ix_env_created_at", "environment_snapshots", ["created_at"])

    # ── adaptive_policy_logs ───────────────────────────────────────
    op.create_table(
        "adaptive_policy_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("gate_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "source",
            sa.Enum("rule_only", "vlm", "vlm_weather", "manual", name="policy_source"),
            nullable=False, server_default="rule_only",
        ),
        sa.Column("profile", sa.String(32), nullable=False),
        sa.Column(
            "risk_level",
            sa.Enum("low", "medium", "high", "critical", name="profile_risk_level"),
            nullable=False,
        ),
        sa.Column("action_tags", sa.JSON(), nullable=False),
        sa.Column("llm_output", sa.JSON(), nullable=True),
        sa.Column("validated_config", sa.JSON(), nullable=False),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("reason", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["environment_snapshots.id"],
            name="fk_policy_snapshot", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_default_charset="utf8mb4",
        mysql_comment="自适应策略审计日志",
    )
    op.create_index("ix_policy_gate_time", "adaptive_policy_logs", ["gate_id", "created_at"])
    op.create_index("ix_policy_profile_time", "adaptive_policy_logs", ["profile", "created_at"])

    # ── access_logs 扩展 ──────────────────────────────────────────
    op.add_column("access_logs", sa.Column("adaptive_profile", sa.String(32), nullable=True, comment="生效的 adaptive profile"))
    op.add_column("access_logs", sa.Column("adaptive_reason", sa.String(1024), nullable=True))
    op.add_column("access_logs", sa.Column("runtime_thresholds", sa.JSON(), nullable=True, comment="生效时的阈值快照"))

    # ── system_configs 种子 ───────────────────────────────────────
    _seed_configs()


def downgrade() -> None:
    op.drop_column("access_logs", "runtime_thresholds")
    op.drop_column("access_logs", "adaptive_reason")
    op.drop_column("access_logs", "adaptive_profile")
    op.drop_index("ix_policy_profile_time", table_name="adaptive_policy_logs")
    op.drop_index("ix_policy_gate_time", table_name="adaptive_policy_logs")
    op.drop_table("adaptive_policy_logs")
    op.execute("DROP TYPE IF EXISTS policy_source")
    op.execute("DROP TYPE IF EXISTS profile_risk_level")
    op.drop_index("ix_env_created_at", table_name="environment_snapshots")
    op.drop_index("ix_env_gate_time", table_name="environment_snapshots")
    op.drop_table("environment_snapshots")


def _seed_configs() -> None:
    """幂等写入自适应默认配置。"""
    configs = [
        ("adaptive.enabled",              '{"value": true}'),
        ("adaptive.mode",                 '{"value": "rule_only"}'),
        ("adaptive.vlm_provider",         '{"value": "deepseek"}'),
        ("adaptive.vlm_interval_seconds", '{"value": 60}'),
        ("adaptive.weather_enabled",      '{"value": false}'),
        ("adaptive.current_profile",      '{"value": "normal"}'),
        ("adaptive.last_reason",          '{"value": "default profile"}'),
        ("adaptive.expires_at",           '{"value": ""}'),
        ("rec.det_thresh.base",           '{"value": 0.50}'),
        ("rec.spoof_thresh.base",         '{"value": 0.85}'),
        ("rec.match_thresh.base",         '{"value": 0.40}'),
        ("rec.quality_thresh.base",       '{"value": 0.50}'),
        ("rec.consensus_frames.base",     '{"value": 3}'),
    ]
    for key, val_json in configs:
        op.execute(
            f"""INSERT INTO system_configs (config_key, value_json, description)
                VALUES ('{key}', CAST('{val_json}' AS JSON), 'adaptive module')
                ON DUPLICATE KEY UPDATE config_key=config_key"""
        )
