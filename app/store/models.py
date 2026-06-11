"""SQLAlchemy 2.0 ORM 模型 · 与 docs/schema.sql 一对一映射（v2 SWU 化）。

设计原则
--------
1. 所有时间字段使用 ``DateTime(timezone=False)`` + ``DATETIME(3)``；应用层统一以
   Asia/Shanghai 写入，数据库不持久化时区。
2. 软删除仅 ``Person`` 启用，实现 ``deleted_at IS NULL`` 视图过滤；其他表硬删。
3. ``FaceEmbedding.id`` 同时是 FAISS 向量 id，**绝不可重置**——见
   ``store/faiss_index.py``。
4. ``SystemConfig.value_json`` 用 MySQL JSON 类型 + Python ``dict`` 互转；
   服务层负责类型校验。
5. 学部→学院→人员 三级层级；``Person.faculty_name`` / ``school_name`` 是冗余字段，
   便于 CSV 导入兜底与大屏聚合。

English summary
---------------
SQLAlchemy 2.0 (async-friendly) declarative models. One-to-one mapping with
docs/schema.sql v2. Embedding row id == FAISS vector id (do not reset).
Faculty → College → Person hierarchy with denormalized text fields on Person
for CSV-import resilience and aggregation speed.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """所有 ORM 模型的根基类。"""


# ---------------------------------------------------------------------------
# 1. faculties (一级单位 · 学部)
# ---------------------------------------------------------------------------


class Faculty(Base):
    """西南大学学部（一级单位）。"""

    __tablename__ = "faculties"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, comment="学部代码，如 faculty_math_info")
    name: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    colleges: Mapped[list["College"]] = relationship(back_populates="faculty")


# ---------------------------------------------------------------------------
# 2. colleges (二级单位 · 学院/研究所)
# ---------------------------------------------------------------------------


class College(Base):
    """西南大学学院/研究所（二级单位）。"""

    __tablename__ = "colleges"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    faculty_id: Mapped[Optional[int]] = mapped_column(
        SmallInteger, ForeignKey("faculties.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    code: Mapped[str] = mapped_column(String(16), unique=True, comment="学院代码（与本科生学号 7-9 位语义对齐）")
    name: Mapped[str] = mapped_column(String(128), unique=True)
    short_name: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    faculty: Mapped[Optional[Faculty]] = relationship(back_populates="colleges")
    persons: Mapped[list["Person"]] = relationship(back_populates="college")


# ---------------------------------------------------------------------------
# 3. admins
# ---------------------------------------------------------------------------


# 多对多关联表：门卫 admin ↔ 所管辖门
# 用 Core Table（而非 ORM 类）即可，因为没有额外业务列，schema 简单。
admin_gate_permissions = Table(
    "admin_gate_permissions",
    Base.metadata,
    Column("admin_id", BigInteger, ForeignKey("admins.id", ondelete="CASCADE"), primary_key=True),
    Column("gate_id", BigInteger, ForeignKey("gates.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime, server_default=func.current_timestamp(), nullable=False),
)


class Admin(Base):
    """管理员账户表（登录系统的人）。

    role 语义：
    - ``superadmin``：全权限（含建/删 admin、改配置、改 schema 字典）
    - ``admin``     ：日常管理（人员/门禁/通行记录可读写，配置只读）
    - ``guard``     ：门卫——只看 ``admin_gate_permissions`` 关联的门相关数据
    - ``viewer``    ：只读访客
    """

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), comment="bcrypt $2b$...")
    name: Mapped[str] = mapped_column(String(128))
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(
        Enum("superadmin", "admin", "guard", "viewer", name="admin_role"),
        default="admin",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # 门卫管辖门（仅当 role='guard' 时使用；其它角色忽略）
    gates: Mapped[list["Gate"]] = relationship(
        secondary=admin_gate_permissions,
        backref="guards",
    )


# ---------------------------------------------------------------------------
# 4. persons
# ---------------------------------------------------------------------------


class Person(Base):
    """已注册人员（本科生 / 研究生 / 教师 / 职工 / 访客）。

    学号约定（西南大学本科生 15 位）：
      222022326062999
      └┴ 学生类型(22) | └────┴ 入学年(2022) | └─┴ 学院代码(326)
                    | └─┴ 班级(062) | └─┴ 班内序号(003)
    研究生学号 / 教工号 长度不等，仅按 ``VARCHAR(32)`` 不强校验，
    业务层（Pydantic）按 role 做差异化校验。
    """

    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True,
        comment="学号（本科 15 位）/ 研究生学号 / 教工号",
    )
    name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(
        Enum("student", "graduate", "teacher", "staff", "visitor", name="person_role"),
        default="student",
        index=True,
        comment="本科生/研究生/教师/职工/访客",
    )
    college_id: Mapped[Optional[int]] = mapped_column(
        SmallInteger, ForeignKey("colleges.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    faculty_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="冗余：学部名")
    school_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="冗余：学院名")
    major: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    class_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="班级，如 2022级06班")
    enrollment_year: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    campus: Mapped[str] = mapped_column(
        Enum("beibei", "rongchang", name="campus_enum"),
        default="beibei",
        index=True,
    )
    dorm_zone: Mapped[Optional[str]] = mapped_column(
        Enum("nan", "zhu", "mei", "li", "ju", "tao", "xing", name="dorm_zone"),
        nullable=True,
        comment="宿舍园区：楠/竹/梅/李/橘/桃/杏",
    )
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("active", "suspended", "graduated", "expired", name="person_status"),
        default="active",
        index=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    college: Mapped[Optional[College]] = relationship(back_populates="persons")
    embeddings: Mapped[list["FaceEmbedding"]] = relationship(
        back_populates="person", cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# 5. face_embeddings
# ---------------------------------------------------------------------------


class FaceEmbedding(Base):
    """人脸嵌入元数据；id 同时是 FAISS 向量 id。"""

    __tablename__ = "face_embeddings"
    __table_args__ = (UniqueConstraint("person_id", "sha256", name="uq_face_embeddings_person_sha"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("persons.id", ondelete="CASCADE"), index=True,
    )
    sha256: Mapped[str] = mapped_column(String(64), comment="原图字节 SHA-256")
    image_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    vector_dim: Mapped[int] = mapped_column(SmallInteger, default=512)
    model_name: Mapped[str] = mapped_column(String(64), comment="如 edgeface_s_gamma_05")
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    person: Mapped[Person] = relationship(back_populates="embeddings")


# ---------------------------------------------------------------------------
# 6. gates
# ---------------------------------------------------------------------------


class Gate(Base):
    """门禁点（北碚校区七门 + 荣昌校区扩展）。"""

    __tablename__ = "gates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    campus: Mapped[str] = mapped_column(
        Enum("beibei", "rongchang", name="gate_campus"),
        default="beibei",
        index=True,
    )
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    direction: Mapped[str] = mapped_column(
        Enum("in", "out", "both", name="gate_direction"),
        default="both",
        comment="通行方向：仅入/仅出/双向",
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("online", "offline", "disabled", name="gate_status"),
        default="offline",
        index=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


# ---------------------------------------------------------------------------
# 7. access_logs
# ---------------------------------------------------------------------------


class AccessLog(Base):
    """通行/识别日志（追加写）。"""

    __tablename__ = "access_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), index=True,
    )
    gate_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("gates.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    matched_person_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("persons.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    visitor_appointment_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("visitor_appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="访客通行时关联的有效预约 id",
    )
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="cos in [-1,1]")
    spoof_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="real prob in [0,1]")
    decision: Mapped[str] = mapped_column(
        Enum("granted", "rejected", "spoof", "no_face", name="access_decision"),
    )
    snapshot_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 环境自适应扩展字段（Phase 2）
    adaptive_profile: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="生效的 adaptive profile",
    )
    adaptive_reason: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True,
    )
    runtime_thresholds: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="生效时的阈值快照",
    )


# ---------------------------------------------------------------------------
# 9. environment_snapshots
# ---------------------------------------------------------------------------


class EnvironmentSnapshot(Base):
    """环境感知快照（VLM / 规则 / 天气融合）。"""

    __tablename__ = "environment_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    gate_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    provider: Mapped[str] = mapped_column(String(32), default="rule")
    location_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    scene_tag: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lighting_quality: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    weather_text: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    cloud_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    visibility_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precipitation_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    irradiance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    humidity_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_day: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    camera_luma_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    camera_luma_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    camera_blur_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    under_exposed_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    over_exposed_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recent_reject_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recent_low_quality_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recent_spoof_reject_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recent_avg_similarity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vlm_raw_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    weather_raw_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(),
    )


# ---------------------------------------------------------------------------
# 10. adaptive_policy_logs
# ---------------------------------------------------------------------------


class AdaptivePolicyLog(Base):
    """自适应策略审计日志。"""

    __tablename__ = "adaptive_policy_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("environment_snapshots.id", ondelete="SET NULL"), nullable=True,
    )
    gate_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(
        Enum("rule_only", "vlm", "vlm_weather", "manual", name="policy_source"),
        default="rule_only",
    )
    profile: Mapped[str] = mapped_column(String(32))
    risk_level: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", "critical", name="profile_risk_level"),
    )
    action_tags: Mapped[dict] = mapped_column(JSON)
    llm_output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    validated_config: Mapped[dict] = mapped_column(JSON)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(),
    )


# ---------------------------------------------------------------------------
# 11. system_configs
# ---------------------------------------------------------------------------


class SystemConfig(Base):
    """全局可调参数（学校身份 / 识别阈值 / UI 主题等）。"""

    __tablename__ = "system_configs"

    config_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSON)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


# ---------------------------------------------------------------------------
# 12. visitor_appointments
# ---------------------------------------------------------------------------


class VisitorAppointment(Base):
    """访客预约记录。"""

    __tablename__ = "visitor_appointments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("persons.id", ondelete="CASCADE"),
    )
    id_card: Mapped[str] = mapped_column(String(32), comment="冗余：身份证号")
    visitor_name: Mapped[str] = mapped_column(String(128), comment="冗余：姓名")
    visit_reason: Mapped[str] = mapped_column(String(512), comment="来访原因")
    arrival_slot: Mapped[int] = mapped_column(
        SmallInteger, comment="到达时间段 0-5",
    )
    departure_slot: Mapped[int] = mapped_column(
        SmallInteger, comment="离开时间段 0-5",
    )
    appointment_date: Mapped[date] = mapped_column(Date, comment="预约日期")
    arrival_date: Mapped[date] = mapped_column(Date, comment="到达日期")
    departure_date: Mapped[date] = mapped_column(Date, comment="离开日期")
    status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected", "expired", "cancelled",
             name="appointment_status"),
        default="pending",
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reject_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(),
    )
