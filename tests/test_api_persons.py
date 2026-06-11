"""人员/学部/学院/Dashboard 路由集成测试。"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.app_factory import create_admin_app


@pytest_asyncio.fixture(loop_scope="session")
async def auth_client():
    app = create_admin_app()
    # httpx ASGITransport 不会触发 lifespan，手动注入 admin app_state
    from app.api.app_factory import _build_admin_state
    app.state.app_state = _build_admin_state()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as c:
        # 登录拿 token
        r = await c.post("/api/auth/login",
                         json={"username": "admin", "password": "test-only-password"})
        assert r.status_code == 200
        token = r.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


# ---------------------------------------------------------------------------
# 学部 / 学院
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_list_faculties(auth_client):
    r = await auth_client.get("/api/system/faculties")
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 12
    # 用户所在学部
    math_info = next(f for f in items if f["code"] == "faculty_math_info")
    assert math_info["name"] == "数学与信息科学学部"
    assert math_info["colleges_count"] >= 4


@pytest.mark.asyncio(loop_scope="session")
async def test_list_colleges_filter_by_faculty(auth_client):
    # 先取数信学部的 id
    r = await auth_client.get("/api/system/faculties")
    fid = next(f["id"] for f in r.json() if f["code"] == "faculty_math_info")

    r = await auth_client.get(f"/api/system/colleges?faculty_id={fid}")
    assert r.status_code == 200
    cs = r.json()
    codes = {c["code"] for c in cs}
    assert "326" in codes      # 计信院
    # 检查数信学部下学院数 >= 4（数统、计信、电信、人工智能）
    assert len(cs) >= 4


# ---------------------------------------------------------------------------
# 系统配置
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_list_configs(auth_client):
    r = await auth_client.get("/api/system/configs")
    assert r.status_code == 200
    keys = {c["config_key"] for c in r.json()}
    assert "school.code" in keys
    assert "ui.theme.primary" in keys


@pytest.mark.asyncio(loop_scope="session")
async def test_update_config_threshold(auth_client):
    r = await auth_client.put(
        "/api/system/configs/recognition.match_threshold",
        json={"value": 0.42},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["value_json"] == {"value": 0.42}

    # 还原默认值，避免污染
    await auth_client.put(
        "/api/system/configs/recognition.match_threshold", json={"value": 0.40},
    )


# ---------------------------------------------------------------------------
# 人员 CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_list_persons_default(auth_client):
    r = await auth_client.get("/api/persons")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["items"], list)
    assert body["total"] >= 0


@pytest.mark.asyncio(loop_scope="session")
async def test_parse_student_id(auth_client):
    r = await auth_client.get("/api/persons/parse-id/222022326062999")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["enrollment_year"] == 2022
    assert body["college_code"] == "326"
    assert body["type_name"] == "本科生"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_person_invalid_student_id(auth_client):
    """非 22 开头、非 15 位的本科生学号必须 422。"""
    r = await auth_client.post("/api/persons", json={
        "external_id": "12345",  # too short for student
        "name": "测试",
        "role": "student",
    })
    assert r.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_person_crud_lifecycle(auth_client, db):
    """CREATE/READ/UPDATE/SOFT-DELETE 全流程。

    使用 999 序号位 + 当前秒级时间戳后两位生成唯一学号，避免与上一次跑测试残留的
    软删记录冲突（external_id UNIQUE 约束不放过 deleted_at IS NOT NULL 的行）。
    末尾 hard-delete 清理。
    """
    import time

    from app.store.models import Person
    from sqlalchemy import select

    suffix = f"{int(time.time()) % 100:02d}"
    sid = f"2220223260629{suffix}"   # 总共 15 位，22 + 2022 + 326 + 0629 + suffix(2)

    # 万一上次没清理：先 hard-delete 同 ID
    existing = await db.scalar(select(Person).where(Person.external_id == sid))
    if existing is not None:
        await db.delete(existing)
        await db.commit()

    # CREATE
    payload = {
        "external_id": sid, "name": "测试人员", "role": "student",
        "campus": "beibei", "dorm_zone": "ju", "enrollment_year": 2022,
    }
    r = await auth_client.post("/api/persons", json=payload)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    try:
        # GET
        r = await auth_client.get(f"/api/persons/{pid}")
        assert r.status_code == 200
        assert r.json()["external_id"] == sid

        # UPDATE
        r = await auth_client.put(f"/api/persons/{pid}", json={"name": "测试人员-改"})
        assert r.status_code == 200
        assert r.json()["name"] == "测试人员-改"

        # SEARCH
        r = await auth_client.get(f"/api/persons?q={suffix}")
        assert any(p["id"] == pid for p in r.json()["items"])

        # DELETE (soft)
        r = await auth_client.delete(f"/api/persons/{pid}")
        assert r.status_code == 200

        # 再 GET 应 404（软删后默认列表/详情排除）
        r = await auth_client.get(f"/api/persons/{pid}")
        assert r.status_code == 404
    finally:
        # Hard-delete 残留以保持 demo_persons_seeded 的 4 条计数稳定
        leftover = await db.scalar(select(Person).where(Person.external_id == sid))
        if leftover is not None:
            await db.delete(leftover)
            await db.commit()


# ---------------------------------------------------------------------------
# 门禁
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_seven_swu_gates_visible(auth_client):
    r = await auth_client.get("/api/gates")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 7
    codes = {g["code"] for g in items}
    assert "gate_hanhong" in codes
    assert "gate_xuexing" in codes


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_dashboard_aggregation(auth_client):
    r = await auth_client.get("/api/system/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    # 学校信息齐全
    assert body["school"]["name_zh"] == "西南大学"
    assert body["school"]["motto"] == "含弘光大，继往开来"
    # 门禁统计
    assert body["gates_total"] == 7
    assert body["gates_online"] >= 2  # 至少 2（含弘 + 学行），实际部署可手动开更多
    # 人员统计
    assert body["persons_total"] >= 4
