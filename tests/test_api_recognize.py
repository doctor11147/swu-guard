"""P6 端到端识别路由测试（**真实加载推理 pipeline**）。

为避免每次 pytest 都加载 ONNX/torch 模型（10s+），本文件用专门 marker
``slow`` 标识，可通过 ``pytest -m "not slow"`` 跳过。CI 中应单独跑。
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


pytestmark = pytest.mark.slow   # 整个文件都标 slow


@pytest_asyncio.fixture(loop_scope="session")
async def full_client():
    """加载完整 pipeline 的 client（含 SCRFD/MiniFAS/EdgeFace + FAISS）。"""
    from app.api.main import create_app

    app = create_app()
    # 手动触发 lifespan
    from app.settings import Settings
    from app.api.state import AppState
    app.state.app_state = AppState.build(Settings.load())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as c:
        # 登录
        r = await c.post(
            "/api/auth/login",
            json={"username": "admin", "password": "test-only-password"},
        )
        assert r.status_code == 200, r.text
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        yield c


@pytest.mark.asyncio(loop_scope="session")
async def test_health_with_full_pipeline(full_client):
    r = await full_client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio(loop_scope="session")
async def test_recognize_image_no_face(full_client):
    """发一张 1x1 黑图，应返回空 faces 列表（pipeline 检测不到人脸）。"""
    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (0, 0, 0)).save(buf, format="JPEG")
    buf.seek(0)

    r = await full_client.post(
        "/api/recognize",
        files={"image": ("black.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "faces" in body
    assert "threshold" in body
    assert body["faces"] == []   # 无人脸
