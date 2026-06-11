"""人员路由 · /api/persons"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentAdmin, DbSession, forbid_guard, require_role
from app.api.state import AppState, get_app_state
from app.schemas.common import OkOut, Page
from app.schemas.persons import (
    PersonCreateIn,
    PersonDetailOut,
    PersonOut,
    PersonUpdateIn,
    StudentIdParseOut,
)
from app.services import persons as persons_svc

router = APIRouter(
    prefix="/persons", tags=["persons"],
    # 整个人员管理域对门卫不可见
    dependencies=[Depends(forbid_guard)],
)


def _person_to_out(p, embedding_count: int = 0) -> PersonOut:
    return PersonOut(
        id=p.id, external_id=p.external_id, name=p.name, role=p.role,
        college_id=p.college_id, faculty_name=p.faculty_name, school_name=p.school_name,
        major=p.major, class_code=p.class_code, enrollment_year=p.enrollment_year,
        campus=p.campus, dorm_zone=p.dorm_zone, phone=p.phone, email=p.email,
        status=p.status, note=p.note,
        created_at=p.created_at, updated_at=p.updated_at,
        embedding_count=embedding_count,
    )


@router.get("", response_model=Page[PersonOut])
async def list_persons(
    db: DbSession,
    _admin: CurrentAdmin,
    q: str | None = None,
    role: str | None = None,
    status_: str | None = Query(None, alias="status"),
    college_id: int | None = None,
    faculty_id: int | None = None,
    campus: str | None = None,
    dorm_zone: str | None = None,
    enrollment_year: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    rows, total = await persons_svc.list_persons(
        db, q=q, role=role, status=status_, college_id=college_id,
        faculty_id=faculty_id, campus=campus, dorm_zone=dorm_zone,
        enrollment_year=enrollment_year, page=page, page_size=page_size,
    )
    return Page[PersonOut](
        items=[_person_to_out(p, cnt) for p, cnt in rows],
        total=total, page=page, page_size=page_size,
    )


@router.get("/parse-id/{external_id}", response_model=StudentIdParseOut)
async def parse_external_id(external_id: str, _admin: CurrentAdmin):
    """前端 helper：解析 SWU 15 位本科生学号。"""
    return StudentIdParseOut.parse(external_id)


@router.get("/{person_id}", response_model=PersonDetailOut)
async def get_person(person_id: int, db: DbSession, _admin: CurrentAdmin):
    try:
        p, cnt = await persons_svc.get_person_with_count(db, person_id)
    except persons_svc.PersonNotFound:
        raise HTTPException(404, {"code": "PERSON_NOT_FOUND", "message": "人员不存在"}) from None
    base = _person_to_out(p, cnt)
    college_name = p.college.name if p.college else p.school_name
    faculty_id = p.college.faculty_id if p.college else None
    return PersonDetailOut(
        **base.model_dump(),
        college_name=college_name,
        faculty_id=faculty_id,
    )


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def create_person(
    payload: PersonCreateIn, db: DbSession, _admin: CurrentAdmin,
):
    try:
        p = await persons_svc.create_person(db, payload)
    except persons_svc.DuplicateExternalId as e:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "PERSON_DUPLICATE_EXTERNAL_ID", "message": str(e)},
        ) from None
    return _person_to_out(p)


@router.put("/{person_id}", response_model=PersonOut)
async def update_person(
    person_id: int, payload: PersonUpdateIn, db: DbSession, _admin: CurrentAdmin,
):
    try:
        p = await persons_svc.update_person(db, person_id, payload)
    except persons_svc.PersonNotFound:
        raise HTTPException(404, {"code": "PERSON_NOT_FOUND", "message": "人员不存在"}) from None
    return _person_to_out(p)


@router.delete("/{person_id}", response_model=OkOut)
async def delete_person(
    person_id: int,
    db: DbSession,
    _admin: CurrentAdmin,
    state: AppState = Depends(get_app_state),
):
    try:
        emb_ids = await persons_svc.soft_delete(db, person_id)
    except persons_svc.PersonNotFound:
        raise HTTPException(404, {"code": "PERSON_NOT_FOUND", "message": "人员不存在"}) from None
    if emb_ids:
        with state.write_lock:
            state.faiss.remove(emb_ids)
            state.faiss.save()
    return OkOut()


@router.post(
    "/{person_id}/restore",
    response_model=PersonOut,
    dependencies=[Depends(require_role("superadmin"))],
)
async def restore_person(person_id: int, db: DbSession):
    try:
        p = await persons_svc.restore_person(db, person_id)
    except persons_svc.PersonNotFound:
        raise HTTPException(404, {"code": "PERSON_NOT_FOUND", "message": "人员不存在"}) from None
    return _person_to_out(p)
