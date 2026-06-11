"""Visitor registration and appointment workflow."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.visitors import SLOT_LABELS, DailySlotsOut, TimeSlotInfo
from app.store.models import FaceEmbedding, Person, VisitorAppointment

CST = timezone(timedelta(hours=8))  # Asia/Shanghai
MAX_PER_SLOT = 20


class AppointmentError(Exception):
    """Business-rule failure for visitor appointment workflow."""


class VisitorError(Exception):
    """Business-rule failure for visitor identity workflow."""


def normalize_id_card(id_card: str) -> str:
    return id_card.strip().upper()


def current_slot(now: datetime | None = None) -> int:
    dt = now or datetime.now(CST)
    return min(dt.hour // 4, 5)


async def register_visitor(
    db: AsyncSession,
    *,
    id_card: str,
    name: str,
    phone: str | None = None,
    email: str | None = None,
    note: str | None = None,
) -> tuple[Person, bool]:
    """Create or update a visitor person row keyed by ID card."""
    normalized = normalize_id_card(id_card)
    person = await db.scalar(select(Person).where(Person.external_id == normalized))
    if person is not None:
        if person.role != "visitor":
            raise VisitorError("该身份证号已被非访客人员占用")
        if person.deleted_at is not None:
            person.deleted_at = None
            person.status = "active"
        person.name = name
        person.phone = phone
        person.email = email
        person.note = note
        await db.commit()
        await db.refresh(person)
        return person, False

    person = Person(
        external_id=normalized,
        name=name,
        role="visitor",
        status="active",
        campus="beibei",
        phone=phone,
        email=email,
        note=note,
    )
    db.add(person)
    await db.commit()
    await db.refresh(person)
    return person, True


async def get_active_visitor_by_id_card(db: AsyncSession, *, id_card: str) -> Person:
    """Return an active visitor person by ID card or raise a visitor-safe error."""
    normalized = normalize_id_card(id_card)
    person = await db.scalar(
        select(Person).where(
            Person.external_id == normalized,
            Person.deleted_at.is_(None),
        ),
    )
    if person is None:
        raise VisitorError("该身份证号尚未注册，请先注册访客身份")
    if person.role != "visitor":
        raise VisitorError("该账户非访客角色")
    if person.status != "active":
        raise VisitorError(f"访客状态为 {person.status}，不可使用")
    return person


async def _embedding_count(db: AsyncSession, person_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count(FaceEmbedding.id)).where(FaceEmbedding.person_id == person_id),
        ) or 0
    )


def _window_key(day: date, slot: int) -> tuple[date, int]:
    return day, slot


def _overlaps(
    start_a: tuple[date, int],
    end_a: tuple[date, int],
    start_b: tuple[date, int],
    end_b: tuple[date, int],
) -> bool:
    return start_a <= end_b and start_b <= end_a


def _assert_valid_window(
    arrival_date: date,
    arrival_slot: int,
    departure_date: date,
    departure_slot: int,
) -> None:
    now = datetime.now(CST)
    today = now.date()
    start = _window_key(arrival_date, arrival_slot)
    end = _window_key(departure_date, departure_slot)
    if end < start:
        raise AppointmentError("离开时间不得早于到达时间")
    if departure_date < today:
        raise AppointmentError("不能预约过去日期")
    if departure_date == today and departure_slot < current_slot(now):
        raise AppointmentError("不能预约已经结束的时间段")


async def create_appointment(
    db: AsyncSession,
    *,
    id_card: str,
    visit_reason: str,
    arrival_date: date,
    departure_date: date,
    arrival_slot: int,
    departure_slot: int,
) -> VisitorAppointment:
    """Submit a visitor appointment linked to an enrolled visitor face."""
    _assert_valid_window(arrival_date, arrival_slot, departure_date, departure_slot)
    person = await get_active_visitor_by_id_card(db, id_card=id_card)
    if await _embedding_count(db, person.id) <= 0:
        raise AppointmentError("该访客尚未注册人脸，请先完成人脸录入")

    rows = (
        await db.execute(
            select(VisitorAppointment).where(
                VisitorAppointment.person_id == person.id,
                VisitorAppointment.status.in_(["pending", "approved"]),
                VisitorAppointment.arrival_date <= departure_date,
                VisitorAppointment.departure_date >= arrival_date,
            ),
        )
    ).scalars().all()
    target_start = _window_key(arrival_date, arrival_slot)
    target_end = _window_key(departure_date, departure_slot)
    for row in rows:
        if _overlaps(
            target_start,
            target_end,
            _window_key(row.arrival_date, row.arrival_slot),
            _window_key(row.departure_date, row.departure_slot),
        ):
            raise AppointmentError("该时间段已有待审批或已通过预约，请勿重复提交")

    apt = VisitorAppointment(
        person_id=person.id,
        id_card=person.external_id,
        visitor_name=person.name,
        visit_reason=visit_reason,
        arrival_slot=arrival_slot,
        departure_slot=departure_slot,
        appointment_date=arrival_date,
        arrival_date=arrival_date,
        departure_date=departure_date,
        status="pending",
    )
    db.add(apt)
    await db.commit()
    await db.refresh(apt)
    return apt


async def review_appointment(
    db: AsyncSession,
    *,
    appointment_id: int,
    admin_id: int,
    action: str,
    reason: str | None = None,
) -> VisitorAppointment:
    """Approve or reject a pending appointment."""
    apt = await db.get(VisitorAppointment, appointment_id)
    if apt is None:
        raise AppointmentError("预约不存在")
    if apt.status != "pending":
        raise AppointmentError(f"预约状态为 {apt.status}，不可审批")

    if action == "approve":
        _assert_valid_window(apt.arrival_date, apt.arrival_slot, apt.departure_date, apt.departure_slot)
        slot_count = await db.scalar(
            select(func.count(VisitorAppointment.id)).where(
                VisitorAppointment.arrival_date == apt.arrival_date,
                VisitorAppointment.arrival_slot == apt.arrival_slot,
                VisitorAppointment.status == "approved",
            ),
        )
        if slot_count and slot_count >= MAX_PER_SLOT:
            raise AppointmentError(f"该时段已满（{MAX_PER_SLOT}/{MAX_PER_SLOT}）")
        apt.status = "approved"
        apt.reject_reason = None
    else:
        reject_reason = (reason or "").strip()
        if not reject_reason:
            raise AppointmentError("拒绝预约必须填写理由")
        apt.status = "rejected"
        apt.reject_reason = reject_reason

    apt.reviewed_by = admin_id
    apt.reviewed_at = datetime.now(CST).replace(tzinfo=None)
    await db.commit()
    await db.refresh(apt)
    return apt


async def cancel_appointment(
    db: AsyncSession,
    *,
    appointment_id: int,
    id_card: str | None = None,
) -> VisitorAppointment:
    """Cancel a pending or approved appointment.

    When id_card is provided, the cancellation is visitor-side and must match
    the appointment owner. Admin-side cancellation passes no id_card.
    """
    apt = await db.get(VisitorAppointment, appointment_id)
    if apt is None:
        raise AppointmentError("预约不存在")
    if id_card is not None and apt.id_card != normalize_id_card(id_card):
        raise AppointmentError("身份证号与预约记录不匹配")
    if apt.status not in ("pending", "approved"):
        raise AppointmentError(f"预约状态为 {apt.status}，不可取消")
    apt.status = "cancelled"
    await db.commit()
    await db.refresh(apt)
    return apt


async def get_daily_slots(
    db: AsyncSession, *, target_date: date,
) -> DailySlotsOut:
    """Return approved appointment counts for all six daily slots."""
    rows = (
        await db.execute(
            select(
                VisitorAppointment.arrival_slot,
                func.count(VisitorAppointment.id),
            )
            .where(
                VisitorAppointment.arrival_date == target_date,
                VisitorAppointment.status == "approved",
            )
            .group_by(VisitorAppointment.arrival_slot),
        )
    ).all()

    booked_map = {r[0]: r[1] for r in rows}
    slots = [
        TimeSlotInfo(
            slot=i,
            label=SLOT_LABELS[i],
            booked=int(booked_map.get(i, 0)),
            max_capacity=MAX_PER_SLOT,
        )
        for i in range(6)
    ]
    return DailySlotsOut(date=target_date, slots=slots)


async def list_appointments(
    db: AsyncSession,
    *,
    status: str | None = None,
    appointment_date: date | None = None,
    person_id: int | None = None,
    id_card: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[VisitorAppointment], int]:
    """Paginate appointments for admin or visitor lookup."""
    stmt = select(VisitorAppointment)
    if status:
        stmt = stmt.where(VisitorAppointment.status == status)
    if appointment_date:
        stmt = stmt.where(
            VisitorAppointment.arrival_date <= appointment_date,
            VisitorAppointment.departure_date >= appointment_date,
        )
    if person_id:
        stmt = stmt.where(VisitorAppointment.person_id == person_id)
    if id_card:
        stmt = stmt.where(VisitorAppointment.id_card == normalize_id_card(id_card))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        await db.execute(
            stmt.order_by(VisitorAppointment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size),
        )
    ).scalars().all()
    return list(rows), int(total)


async def check_valid_appointment(
    db: AsyncSession,
    *,
    person_id: int,
    now: datetime | None = None,
) -> VisitorAppointment | None:
    """Return the current approved appointment that authorizes a visitor."""
    dt = now or datetime.now(CST)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    today = dt.date()
    slot = current_slot(dt)

    return await db.scalar(
        select(VisitorAppointment)
        .where(
            VisitorAppointment.person_id == person_id,
            VisitorAppointment.status == "approved",
            VisitorAppointment.arrival_date <= today,
            VisitorAppointment.departure_date >= today,
            (
                (VisitorAppointment.arrival_date < today)
                | (VisitorAppointment.arrival_slot <= slot)
            ),
            (
                (VisitorAppointment.departure_date > today)
                | (VisitorAppointment.departure_slot >= slot)
            ),
        )
        .order_by(VisitorAppointment.created_at.desc())
        .limit(1),
    )


async def expire_stale_appointments(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    """Mark approved appointments whose time window has ended as expired."""
    dt = now or datetime.now(CST)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    today = dt.date()
    slot = current_slot(dt)

    stmt = (
        update(VisitorAppointment)
        .where(
            VisitorAppointment.status == "approved",
            (
                (VisitorAppointment.departure_date < today)
                | (
                    (VisitorAppointment.departure_date == today)
                    & (VisitorAppointment.departure_slot < slot)
                )
            ),
        )
        .values(status="expired")
    )
    result = await db.execute(stmt)
    await db.commit()
    return int(result.rowcount or 0)
