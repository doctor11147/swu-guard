"""系统配置 / 学部 / 学院 / Dashboard 路由 · /api/system"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentAdmin, DbSession, GateScope, require_role
from app.schemas.common import OkOut
from app.schemas.persons import (
    CollegeCreateIn,
    CollegeOut,
    CollegeUpdateIn,
    FacultyDetailOut,
)
from app.schemas.system import ConfigOut, ConfigUpdateIn, DashboardOut
from app.services import system as system_svc
from app.store.models import College, Faculty

router = APIRouter(prefix="/system", tags=["system"])


# ---------------------------------------------------------------------------
# Faculties
# ---------------------------------------------------------------------------


@router.get("/faculties", response_model=list[FacultyDetailOut])
async def list_faculties(db: DbSession, _admin: CurrentAdmin):
    rows = await system_svc.list_faculties(db)
    return [
        FacultyDetailOut(
            id=f.id, code=f.code, name=f.name, is_active=f.is_active, colleges_count=cnt,
        )
        for f, cnt in rows
    ]


@router.get("/faculties/{faculty_id}", response_model=FacultyDetailOut)
async def get_faculty(faculty_id: int, db: DbSession, _admin: CurrentAdmin):
    f = await db.get(Faculty, faculty_id)
    if f is None:
        raise HTTPException(404, {"code": "FACULTY_NOT_FOUND", "message": "faculty 不存在"})
    colleges = await system_svc.list_colleges(db, faculty_id=faculty_id)
    return FacultyDetailOut(
        id=f.id, code=f.code, name=f.name, is_active=f.is_active, colleges_count=len(colleges),
    )


# ---------------------------------------------------------------------------
# Colleges
# ---------------------------------------------------------------------------


@router.get("/colleges", response_model=list[CollegeOut])
async def list_colleges(
    db: DbSession,
    _admin: CurrentAdmin,
    faculty_id: int | None = None,
    active: bool | None = None,
    q: str | None = None,
):
    rows = await system_svc.list_colleges(db, faculty_id=faculty_id, active=active, q=q)
    return [CollegeOut.model_validate(c) for c in rows]


@router.post("/colleges", response_model=CollegeOut, dependencies=[Depends(require_role("superadmin"))])
async def create_college(payload: CollegeCreateIn, db: DbSession):
    c = College(**payload.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return CollegeOut.model_validate(c)


@router.put("/colleges/{college_id}", response_model=CollegeOut, dependencies=[Depends(require_role("superadmin"))])
async def update_college(college_id: int, payload: CollegeUpdateIn, db: DbSession):
    c = await db.get(College, college_id)
    if c is None:
        raise HTTPException(404, {"code": "COLLEGE_NOT_FOUND", "message": "college 不存在"})
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    await db.commit()
    await db.refresh(c)
    return CollegeOut.model_validate(c)


@router.delete("/colleges/{college_id}", response_model=OkOut, dependencies=[Depends(require_role("superadmin"))])
async def delete_college(college_id: int, db: DbSession):
    from sqlalchemy import func, select

    from app.store.models import Person

    c = await db.get(College, college_id)
    if c is None:
        raise HTTPException(404, {"code": "COLLEGE_NOT_FOUND", "message": "college 不存在"})
    cnt = await db.scalar(select(func.count(Person.id)).where(Person.college_id == college_id)) or 0
    if cnt > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": "COLLEGE_HAS_PERSONS", "message": f"该学院下仍有 {cnt} 名人员，不能删除"},
        )
    await db.delete(c)
    await db.commit()
    return OkOut()


# ---------------------------------------------------------------------------
# System configs
# ---------------------------------------------------------------------------


@router.get("/configs", response_model=list[ConfigOut])
async def list_configs(db: DbSession, _admin: CurrentAdmin):
    return [ConfigOut.model_validate(c) for c in await system_svc.list_configs(db)]


@router.get("/configs/{key}", response_model=ConfigOut)
async def get_config(key: str, db: DbSession, _admin: CurrentAdmin):
    try:
        c = await system_svc.get_config(db, key)
    except system_svc.ConfigNotFound:
        raise HTTPException(404, {"code": "CONFIG_NOT_FOUND", "message": f"config {key} 不存在"}) from None
    return ConfigOut.model_validate(c)


@router.put("/configs/{key}", response_model=ConfigOut, dependencies=[Depends(require_role("superadmin", "admin"))])
async def update_config(key: str, payload: ConfigUpdateIn, db: DbSession, admin: CurrentAdmin):
    try:
        c = await system_svc.update_config(db, key, payload.value, updated_by=admin.id)
    except system_svc.ConfigNotFound:
        raise HTTPException(404, {"code": "CONFIG_NOT_FOUND", "message": f"config {key} 不存在"}) from None
    return ConfigOut.model_validate(c)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(db: DbSession, _admin: CurrentAdmin, scope: GateScope):
    data = await system_svc.dashboard(db, gate_scope=scope)
    return DashboardOut.model_validate(data)
