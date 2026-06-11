"""认证路由 + 受保护路由集成测试。"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.app_factory import create_admin_app


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    app = create_admin_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as c:
        yield c


@pytest.mark.asyncio(loop_scope="session")
async def test_health_open(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


@pytest.mark.asyncio(loop_scope="session")
async def test_login_wrong_password(client):
    r = await client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong"},
    )
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.asyncio(loop_scope="session")
async def test_login_success_and_me(client):
    # 默认密码由 P4 的 seed_admin 注入
    r = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-only-password"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body
    assert body["user"]["username"] == "admin"
    assert body["user"]["role"] == "superadmin"

    # 用 token 访问 /me
    token = body["access_token"]
    r2 = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["username"] == "admin"


@pytest.mark.asyncio(loop_scope="session")
async def test_protected_without_token(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_protected_with_garbage_token(client):
    r = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "AUTH_INVALID_CREDENTIALS"
