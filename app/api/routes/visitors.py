"""访客预约路由 · /api/visitors"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentAdmin, DbSession
from app.api.state import AppState, get_app_state
from app.schemas.common import Page
from app.schemas.visitors import (
    AppointmentCancelIn,
    AppointmentCreateIn,
    AppointmentLookupIn,
    AppointmentOut,
    AppointmentReviewIn,
    DailySlotsOut,
    VisitorFaceRegisterOut,
    VisitorRegisterIn,
    VisitorRegisterOut,
)
from app.services.face_registration import register_face_images
from app.services import visitors as visitor_svc

router = APIRouter(
    prefix="/visitors",
    tags=["visitors"],
    # 门卫可看预约（审批权限），但人员管理（persons 域）对门卫不可见
)


def _to_out(apt) -> AppointmentOut:
    return AppointmentOut(
        id=apt.id, person_id=apt.person_id, id_card=apt.id_card,
        visitor_name=apt.visitor_name, visit_reason=apt.visit_reason,
        arrival_slot=apt.arrival_slot, departure_slot=apt.departure_slot,
        appointment_date=apt.appointment_date,
        arrival_date=apt.arrival_date,
        departure_date=apt.departure_date,
        status=apt.status,
        reviewed_by=apt.reviewed_by, reviewed_at=apt.reviewed_at,
        reject_reason=apt.reject_reason,
        created_at=apt.created_at, updated_at=apt.updated_at,
    )


# ── 访客侧（无需登录，凭身份证号操作）──────────────────────────


@router.post("/register", response_model=VisitorRegisterOut, status_code=status.HTTP_201_CREATED)
async def register_visitor(
    payload: VisitorRegisterIn,
    db: DbSession,
):
    """访客自助注册身份。身份证号即访客身份主键，后续需继续录入人脸。"""
    try:
        person, created = await visitor_svc.register_visitor(
            db,
            id_card=payload.id_card,
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
            note=payload.note,
        )
    except visitor_svc.VisitorError as e:
        raise HTTPException(409, {"code": "VISITOR_ERROR", "message": str(e)}) from None
    return VisitorRegisterOut(
        person_id=person.id,
        id_card=person.external_id,
        name=person.name,
        status=person.status,
        created=created,
    )


@router.post("/faces", response_model=VisitorFaceRegisterOut)
async def register_visitor_faces(
    id_card: str,
    db: DbSession,
    images: list[UploadFile] = File(..., description="One or more face photos"),
    state: AppState = Depends(get_app_state),
):
    """访客自助录入人脸。与管理员录入共用同一套检测/活体/质量/FAISS 写入逻辑。"""
    if not images:
        raise HTTPException(400, {"code": "NO_IMAGES", "message": "请上传至少一张图"})
    try:
        person = await visitor_svc.get_active_visitor_by_id_card(db, id_card=id_card)
    except visitor_svc.VisitorError as e:
        raise HTTPException(409, {"code": "VISITOR_ERROR", "message": str(e)}) from None
    summary = await register_face_images(db, person=person, images=images, state=state)
    return VisitorFaceRegisterOut(
        person_id=person.id,
        id_card=person.external_id,
        **summary.to_dict(),
    )


@router.post("/appointments", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreateIn,
    db: DbSession,
):
    """提交预约（公开端点：访客凭身份证号提交，无需登录）。访客必须先注册人脸。"""
    try:
        if payload.arrival_date is None or payload.departure_date is None:
            raise visitor_svc.AppointmentError("请选择到达日期和离开日期")
        apt = await visitor_svc.create_appointment(
            db,
            id_card=payload.id_card,
            visit_reason=payload.visit_reason,
            arrival_date=payload.arrival_date,
            departure_date=payload.departure_date,
            arrival_slot=payload.arrival_slot,
            departure_slot=payload.departure_slot,
        )
    except (visitor_svc.AppointmentError, visitor_svc.VisitorError) as e:
        raise HTTPException(409, {"code": "APPOINTMENT_ERROR", "message": str(e)}) from None
    return _to_out(apt)


@router.post("/appointments/lookup", response_model=Page[AppointmentOut])
async def lookup_my_appointments(
    payload: AppointmentLookupIn,
    db: DbSession,
    status_: str | None = Query(None, alias="status"),
    date_: date | None = Query(None, alias="date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """访客凭身份证号查询本人预约记录。"""
    await visitor_svc.expire_stale_appointments(db)
    rows, total = await visitor_svc.list_appointments(
        db,
        status=status_,
        appointment_date=date_,
        id_card=payload.id_card,
        page=page,
        page_size=page_size,
    )
    return Page[AppointmentOut](
        items=[_to_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put("/appointments/{appointment_id}/cancel-by-visitor", response_model=AppointmentOut)
async def cancel_appointment_by_visitor(
    appointment_id: int,
    payload: AppointmentCancelIn,
    db: DbSession,
):
    """访客凭身份证号撤销自己的待审批/已通过预约。"""
    try:
        apt = await visitor_svc.cancel_appointment(
            db,
            appointment_id=appointment_id,
            id_card=payload.id_card,
        )
    except visitor_svc.AppointmentError as e:
        raise HTTPException(409, {"code": "APPOINTMENT_ERROR", "message": str(e)}) from None
    return _to_out(apt)


# ── 审批侧（需管理员/门卫登录）────────────────────────────────


@router.get("/appointments", response_model=Page[AppointmentOut])
async def list_appointments(
    db: DbSession,
    _admin: CurrentAdmin,
    status: str | None = None,
    date_: date | None = Query(None, alias="date"),
    person_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """分页查询预约。"""
    await visitor_svc.expire_stale_appointments(db)
    rows, total = await visitor_svc.list_appointments(
        db, status=status, appointment_date=date_,
        person_id=person_id, page=page, page_size=page_size,
    )
    return Page[AppointmentOut](
        items=[_to_out(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.get("/slots", response_model=DailySlotsOut)
async def daily_slots(
    db: DbSession,
    _admin: CurrentAdmin,
    date_: date = Query(..., alias="date"),
):
    """查询某日各时段预约容量。"""
    await visitor_svc.expire_stale_appointments(db)
    return await visitor_svc.get_daily_slots(db, target_date=date_)


@router.put("/appointments/{appointment_id}/review", response_model=AppointmentOut)
async def review_appointment(
    appointment_id: int,
    payload: AppointmentReviewIn,
    db: DbSession,
    admin: CurrentAdmin,
):
    """审批预约（通过 / 拒绝）。"""
    try:
        apt = await visitor_svc.review_appointment(
            db,
            appointment_id=appointment_id,
            admin_id=admin.id,
            action=payload.action,
            reason=payload.reason,
        )
    except visitor_svc.AppointmentError as e:
        raise HTTPException(409, {"code": "APPOINTMENT_ERROR", "message": str(e)}) from None
    return _to_out(apt)


@router.put("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
async def cancel_appointment(
    appointment_id: int,
    db: DbSession,
    _admin: CurrentAdmin,
):
    """取消预约。"""
    try:
        apt = await visitor_svc.cancel_appointment(db, appointment_id=appointment_id)
    except visitor_svc.AppointmentError as e:
        raise HTTPException(409, {"code": "APPOINTMENT_ERROR", "message": str(e)}) from None
    return _to_out(apt)
