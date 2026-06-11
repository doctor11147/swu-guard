"""VLM provider 工厂 — 按系统配置返回对应 provider 实例。"""

from __future__ import annotations

import os

from app.services.vlm.base import VLMProvider
from app.services.vlm.deepseek_provider import DeepSeekProvider
from app.services.vlm.mock_provider import MockProvider
from app.services.vlm.vectorengine_provider import VectorEngineProvider

def get_provider(provider_name: str = "vectorengine") -> VLMProvider:
    """返回 VLM provider 实例。

    - ``"vectorengine"`` → VectorEngineProvider（GPT-4o vision，推荐）
    - ``"deepseek"``     → DeepSeekProvider（纯文本，不支持视觉）
    - ``"mock"`` / 其他  → MockProvider（离线演示，luma → profile 规则映射）
    """
    name = provider_name.lower()
    if name == "vectorengine":
        return VectorEngineProvider(api_key=os.getenv("VECTORENGINE_API_KEY"))
    if name == "deepseek":
        return DeepSeekProvider(api_key=os.getenv("DEEPSEEK_API_KEY"))
    return MockProvider()
