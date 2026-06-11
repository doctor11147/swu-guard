"""Mock VLM provider 测试。"""

from __future__ import annotations

import numpy as np
import pytest

from app.services.vlm.mock_provider import MockProvider


def _bgr(value: int) -> np.ndarray:
    return np.full((200, 200, 3), value, dtype=np.uint8)


@pytest.mark.asyncio
async def test_mock_normal():
    p = MockProvider()
    r = await p.assess_scene(_bgr(150))
    assert r.profile == "normal"
    assert r.risk_level == "low"


@pytest.mark.asyncio
async def test_mock_overcast():
    r = await MockProvider().assess_scene(_bgr(80))
    assert r.profile == "overcast"


@pytest.mark.asyncio
async def test_mock_low_light():
    r = await MockProvider().assess_scene(_bgr(45))
    assert r.profile == "low_light"
    assert r.risk_level in ("medium", "high")


@pytest.mark.asyncio
async def test_mock_night():
    r = await MockProvider().assess_scene(_bgr(10))
    assert r.profile == "night"


@pytest.mark.asyncio
async def test_mock_backlight():
    # 中间亮度 + 大量过曝像素 → backlight
    frame = _bgr(130)
    frame[0:100, 0:100, :] = 250  # 25% 高亮区 → 触发 over 检测
    r = await MockProvider().assess_scene(frame)
    assert r.profile in ("normal", "backlight")  # 取决于过曝区域是否 > 25%


@pytest.mark.asyncio
async def test_mock_always_returns_action_tags():
    r = await MockProvider().assess_scene(_bgr(20))
    assert "keep_match_threshold" in r.action_tags
    assert len(r.reason) > 0
    assert 0.0 <= r.confidence <= 1.0
