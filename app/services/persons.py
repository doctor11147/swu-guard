"""人员业务逻辑 · CRUD + 学院冗余字段同步。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.schemas.persons import PersonCreateIn, PersonUpdateIn
from app.store.models import College, FaceEmbedding, Person


class PersonError(Exception):
    code = "PERSON_ERROR"


class PersonNotFound(PersonError):
    code = "PERSON_NOT_FOUND"


class DuplicateExternalId(PersonError):
    code = "PERSON_DUPLICATE_EXTERNAL_ID"


async def _sync_denorm(db: AsyncSession, person: Person, college_id: int | None) -> None:
    """根据 college_id 同步 person.school_name / faculty_name 冗余字段。"""
    if college_id is None:
        person.school_name = None
        person.faculty_name = None
        return
    college = await db.scalar(
        select(College).options(selectinload(College.faculty)).where(College.id == college_id),
    )
    if college is None:
        person.school_name = None
        person.faculty_name = None
        return
    person.school_name = college.name
    person.faculty_name = college.faculty.name if college.faculty else None


async def list_persons(
    db: AsyncSession,
    *,
    q: str | None = None,
    role: str | None = None,
    status: str | None = None,
    college_id: int | None = None,
    faculty_id: int | None = None,
    campus: str | None = None,
    dorm_zone: str | None = None,
    enrollment_year: int | None = None,
    include_deleted: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[Person, int]], int]:
    """返回 ``([(person, embedding_count), ...], total)``。

    用 LEFT OUTER JOIN + GROUP BY 的方式一次性带回每人的样本数，避免在
    路由层做 N+1 查询。
    """
    stmt = select(Person)
    if not include_deleted:
        stmt = stmt.where(Person.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Person.external_id.like(like),
            Person.name.like(like),
            Person.school_name.like(like),
            Person.major.like(like),
        ))
    if role:
        stmt = stmt.where(Person.role == role)
    if status:
        stmt = stmt.where(Person.status == status)
    if college_id is not None:
        stmt = stmt.where(Person.college_id == college_id)
    if faculty_id is not None:
        # 通过 college 关联的 faculty 过滤
        stmt = stmt.join(College, Person.college_id == College.id).where(
            College.faculty_id == faculty_id,
        )
    if campus:
        stmt = stmt.where(Person.campus == campus)
    if dorm_zone:
        stmt = stmt.where(Person.dorm_zone == dorm_zone)
    if enrollment_year is not None:
        stmt = stmt.where(Person.enrollment_year == enrollment_year)

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    # 在 person 选择上 outer-join face_embeddings 并按 person 聚合计数。
    listing = (
        stmt.add_columns(func.count(FaceEmbedding.id).label("emb_count"))
        .outerjoin(FaceEmbedding, FaceEmbedding.person_id == Person.id)
        .group_by(Person.id)
        .order_by(Person.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(listing)).all()
    return [(p, int(cnt or 0)) for p, cnt in rows], int(total)


async def get_person_with_count(db: AsyncSession, person_id: int) -> tuple[Person, int]:
    """获取人员 + eager-load college（含 faculty）。

    async session 不允许在路由/路由 helper 里 lazy-load 关系，否则会抛
    ``MissingGreenlet``，FastAPI 上抛 500。此处一次性 selectinload。
    """
    p = await db.scalar(
        select(Person)
        .options(selectinload(Person.college).selectinload(College.faculty))
        .where(Person.id == person_id),
    )
    if p is None or p.deleted_at is not None:
        raise PersonNotFound(f"person id={person_id} not found")
    cnt = await db.scalar(
        select(func.count(FaceEmbedding.id)).where(FaceEmbedding.person_id == person_id),
    ) or 0
    return p, int(cnt)


async def create_person(db: AsyncSession, payload: PersonCreateIn) -> Person:
    existing = await db.scalar(
        select(Person).where(Person.external_id == payload.external_id),
    )
    if existing is not None:
        raise DuplicateExternalId(f"学号/工号 {payload.external_id} 已存在")
    p = Person(**payload.model_dump(exclude={"college_id"}))
    p.college_id = payload.college_id
    await _sync_denorm(db, p, payload.college_id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def update_person(db: AsyncSession, person_id: int, payload: PersonUpdateIn) -> Person:
    p, _ = await get_person_with_count(db, person_id)
    data = payload.model_dump(exclude_unset=True)
    college_changed = "college_id" in data
    for k, v in data.items():
        setattr(p, k, v)
    if college_changed:
        await _sync_denorm(db, p, p.college_id)
    await db.commit()
    await db.refresh(p)
    return p


async def soft_delete(db: AsyncSession, person_id: int) -> list[int]:
    """标记软删除，返回该人员所有 face_embedding 的 id（路由层从 FAISS 移除）。"""
    p = await db.get(Person, person_id)
    if p is None:
        raise PersonNotFound(f"person id={person_id} not found")
    embedding_ids = list(await db.scalars(
        select(FaceEmbedding.id).where(FaceEmbedding.person_id == person_id),
    ))
    p.deleted_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    p.status = "expired"
    # 真正物理删除嵌入：保持 FAISS 与 DB 一致（软删人员后向量库不应再命中）
    await db.execute(
        delete(FaceEmbedding).where(FaceEmbedding.person_id == person_id),
    )
    await db.commit()
    return [int(i) for i in embedding_ids]


async def restore_person(db: AsyncSession, person_id: int) -> Person:
    p = await db.get(Person, person_id)
    if p is None:
        raise PersonNotFound(f"person id={person_id} not found")
    p.deleted_at = None
    p.status = "active"
    await db.commit()
    await db.refresh(p)
    return p
