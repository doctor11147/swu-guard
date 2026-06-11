"""Visitor registration and appointment workflow tests."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.app_factory import _build_admin_state, create_admin_app
from app.store.models import FaceEmbedding, Person, VisitorAppointment


@pytest_asyncio.fixture(loop_scope="session")
async def auth_client():
    app = create_admin_app()
    app.state.app_state = _build_admin_state()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        r = await c.post(
            "/api/auth/login",
            json={"username": "admin", "password": "test-only-password"},
        )
        assert r.status_code == 200, r.text
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        yield c


async def _cleanup(db, id_card: str) -> None:
    person = await db.scalar(select(Person).where(Person.external_id == id_card))
    if person is not None:
        await db.execute(delete(VisitorAppointment).where(VisitorAppointment.person_id == person.id))
        await db.execute(delete(FaceEmbedding).where(FaceEmbedding.person_id == person.id))
        await db.delete(person)
        await db.commit()


def _future_date_and_slots() -> tuple[str, int, int]:
    tomorrow = date.today() + timedelta(days=1)
    return tomorrow.isoformat(), 2, 3


def _cross_day_window() -> tuple[str, int, str, int]:
    start = date.today() + timedelta(days=1)
    end = start + timedelta(days=1)
    return start.isoformat(), 4, end.isoformat(), 1


@pytest.mark.asyncio(loop_scope="session")
async def test_visitor_appointment_requires_registered_face(auth_client, db):
    id_card = "50010119900101123X"
    await _cleanup(db, id_card)

    try:
        r = await auth_client.post(
            "/api/visitors/register",
            json={
                "id_card": id_card.lower(),
                "name": "访客甲",
                "phone": "13800000000",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["id_card"] == id_card
        assert body["created"] is True
        person_id = body["person_id"]

        appointment_date, arrival_slot, departure_slot = _future_date_and_slots()
        r = await auth_client.post(
            "/api/visitors/appointments",
            json={
                "id_card": id_card,
                "visit_reason": "参加学院访谈",
                "arrival_date": appointment_date,
                "departure_date": appointment_date,
                "arrival_slot": arrival_slot,
                "departure_slot": departure_slot,
            },
        )
        assert r.status_code == 409
        assert "人脸" in r.text

        db.add(FaceEmbedding(
            person_id=person_id,
            sha256="a" * 64,
            image_path="test.jpg",
            vector_dim=512,
            model_name="edgeface_s_gamma_05",
            quality_score=0.9,
        ))
        await db.commit()

        r = await auth_client.post(
            "/api/visitors/appointments",
            json={
                "id_card": id_card,
                "visit_reason": "参加学院访谈",
                "arrival_date": appointment_date,
                "departure_date": appointment_date,
                "arrival_slot": arrival_slot,
                "departure_slot": departure_slot,
            },
        )
        assert r.status_code == 201, r.text
        apt = r.json()
        assert apt["status"] == "pending"
        assert apt["person_id"] == person_id
    finally:
        await _cleanup(db, id_card)


@pytest.mark.asyncio(loop_scope="session")
async def test_visitor_review_validity_and_expiration(auth_client, db):
    from app.services.visitors import check_valid_appointment, expire_stale_appointments

    id_card = "500101199002021234"
    await _cleanup(db, id_card)

    try:
        r = await auth_client.post(
            "/api/visitors/register",
            json={"id_card": id_card, "name": "访客乙"},
        )
        assert r.status_code == 201, r.text
        person_id = r.json()["person_id"]
        db.add(FaceEmbedding(
            person_id=person_id,
            sha256="b" * 64,
            image_path="test.jpg",
            vector_dim=512,
            model_name="edgeface_s_gamma_05",
            quality_score=0.9,
        ))
        await db.commit()

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = await auth_client.post(
            "/api/visitors/appointments",
            json={
                "id_card": id_card,
                "visit_reason": "设备维护",
                "arrival_date": tomorrow,
                "departure_date": tomorrow,
                "arrival_slot": 0,
                "departure_slot": 5,
            },
        )
        assert r.status_code == 201, r.text
        apt_id = r.json()["id"]

        r = await auth_client.put(
            f"/api/visitors/appointments/{apt_id}/review",
            json={"action": "reject"},
        )
        assert r.status_code == 422

        r = await auth_client.put(
            f"/api/visitors/appointments/{apt_id}/review",
            json={"action": "approve"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "approved"

        valid = await check_valid_appointment(
            db,
            person_id=person_id,
            now=datetime.combine(
                date.today() + timedelta(days=1),
                datetime.min.time(),
                tzinfo=timezone(timedelta(hours=8)),
            ) + timedelta(hours=8),
        )
        assert valid is not None
        assert valid.id == apt_id

        expired = await expire_stale_appointments(
            db,
            now=datetime.now(timezone(timedelta(hours=8))) + timedelta(days=2),
        )
        assert expired >= 1
        refreshed = await db.get(VisitorAppointment, apt_id)
        assert refreshed is not None
        assert refreshed.status == "expired"
    finally:
        await _cleanup(db, id_card)


@pytest.mark.asyncio(loop_scope="session")
async def test_visitor_lookup_and_cancel_own_appointment(auth_client, db):
    id_card = "500101199003031234"
    await _cleanup(db, id_card)

    try:
        r = await auth_client.post(
            "/api/visitors/register",
            json={"id_card": id_card, "name": "访客丙"},
        )
        assert r.status_code == 201, r.text
        person_id = r.json()["person_id"]
        db.add(FaceEmbedding(
            person_id=person_id,
            sha256="c" * 64,
            image_path="test.jpg",
            vector_dim=512,
            model_name="edgeface_s_gamma_05",
            quality_score=0.9,
        ))
        await db.commit()

        appointment_date, arrival_slot, departure_slot = _future_date_and_slots()
        r = await auth_client.post(
            "/api/visitors/appointments",
            json={
                "id_card": id_card,
                "visit_reason": "参观实验室",
                "arrival_date": appointment_date,
                "departure_date": appointment_date,
                "arrival_slot": arrival_slot,
                "departure_slot": departure_slot,
            },
        )
        assert r.status_code == 201, r.text
        apt_id = r.json()["id"]

        r = await auth_client.post(
            "/api/visitors/appointments/lookup",
            json={"id_card": id_card},
        )
        assert r.status_code == 200, r.text
        assert r.json()["total"] >= 1

        r = await auth_client.put(
            f"/api/visitors/appointments/{apt_id}/cancel-by-visitor",
            json={"id_card": "500101199004041234"},
        )
        assert r.status_code == 409

        r = await auth_client.put(
            f"/api/visitors/appointments/{apt_id}/cancel-by-visitor",
            json={"id_card": id_card},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"
    finally:
        await _cleanup(db, id_card)


@pytest.mark.asyncio(loop_scope="session")
async def test_visitor_lookup_expires_stale_approved_appointment(auth_client, db):
    id_card = "500101199006061234"
    await _cleanup(db, id_card)

    try:
        r = await auth_client.post(
            "/api/visitors/register",
            json={"id_card": id_card, "name": "访客戊"},
        )
        assert r.status_code == 201, r.text
        person_id = r.json()["person_id"]

        stale_date = date.today() - timedelta(days=1)
        apt = VisitorAppointment(
            person_id=person_id,
            id_card=id_card,
            visitor_name="访客戊",
            visit_reason="历史访问",
            appointment_date=stale_date,
            arrival_date=stale_date,
            departure_date=stale_date,
            arrival_slot=0,
            departure_slot=1,
            status="approved",
        )
        db.add(apt)
        await db.commit()
        await db.refresh(apt)
        apt_id = apt.id

        r = await auth_client.post(
            "/api/visitors/appointments/lookup",
            json={"id_card": id_card},
        )
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert items[0]["id"] == apt_id
        assert items[0]["status"] == "expired"

        await db.rollback()
        refreshed = await db.get(VisitorAppointment, apt_id)
        assert refreshed is not None
        await db.refresh(refreshed)
        assert refreshed.status == "expired"
    finally:
        await _cleanup(db, id_card)


@pytest.mark.asyncio(loop_scope="session")
async def test_visitor_cross_day_appointment_window(auth_client, db):
    from app.services.visitors import check_valid_appointment, expire_stale_appointments

    id_card = "500101199005051234"
    await _cleanup(db, id_card)

    try:
        r = await auth_client.post(
            "/api/visitors/register",
            json={"id_card": id_card, "name": "访客丁"},
        )
        assert r.status_code == 201, r.text
        person_id = r.json()["person_id"]
        db.add(FaceEmbedding(
            person_id=person_id,
            sha256="d" * 64,
            image_path="test.jpg",
            vector_dim=512,
            model_name="edgeface_s_gamma_05",
            quality_score=0.9,
        ))
        await db.commit()

        arrival_date, arrival_slot, departure_date, departure_slot = _cross_day_window()
        r = await auth_client.post(
            "/api/visitors/appointments",
            json={
                "id_card": id_card,
                "visit_reason": "跨天学术访问",
                "arrival_date": arrival_date,
                "arrival_slot": arrival_slot,
                "departure_date": departure_date,
                "departure_slot": departure_slot,
            },
        )
        assert r.status_code == 201, r.text
        apt = r.json()
        assert apt["arrival_date"] == arrival_date
        assert apt["departure_date"] == departure_date
        apt_id = apt["id"]

        r = await auth_client.put(
            f"/api/visitors/appointments/{apt_id}/review",
            json={"action": "approve"},
        )
        assert r.status_code == 200, r.text

        cst = timezone(timedelta(hours=8))
        valid = await check_valid_appointment(
            db,
            person_id=person_id,
            now=datetime.combine(
                date.fromisoformat(arrival_date),
                datetime.min.time(),
                tzinfo=cst,
            ) + timedelta(hours=18),
        )
        assert valid is not None
        assert valid.id == apt_id

        valid = await check_valid_appointment(
            db,
            person_id=person_id,
            now=datetime.combine(
                date.fromisoformat(departure_date),
                datetime.min.time(),
                tzinfo=cst,
            ) + timedelta(hours=9),
        )
        assert valid is None

        expired = await expire_stale_appointments(
            db,
            now=datetime.combine(
                date.fromisoformat(departure_date),
                datetime.min.time(),
                tzinfo=cst,
            ) + timedelta(hours=9),
        )
        assert expired >= 1
    finally:
        await _cleanup(db, id_card)
