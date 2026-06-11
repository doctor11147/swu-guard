"""VectorEngine / OpenAI-compatible VLM Provider.

VectorEngine (api.vectorengine.ai) is an OpenAI-compatible API proxy.
It routes to GPT-4o which has native vision support.  Provider works
with any OpenAI-compatible endpoint — just change base_url / model.

Uses ``http.client`` to avoid ``httpx`` TLS issues on macOS.
"""

from __future__ import annotations

import asyncio
import base64
import http.client
import json
import os

import cv2
import numpy as np

from app.schemas.adaptive import VLMSceneAssessment
from app.services.vlm.base import VLMError, VLMProvider

DEFAULT_BASE_URL = "api.vectorengine.ai"
DEFAULT_MODEL = "gpt-4o"
REQUEST_TIMEOUT = 25  # 视觉请求比纯文本稍慢

_SYSTEM_PROMPT = """你是校园门禁系统的环境风险分析器。你只能观察门禁摄像头画面中的环境、光照、曝光、可见度和画面质量。你不能识别人名，不能判断身份，不能决定是否放行。请输出严格 JSON，字段包括 scene_tag, lighting_quality, face_visibility, risk_level, profile, action_tags, reason, confidence。你不能输出任何具体识别阈值。低光照、逆光、雨雾或画面不可用时，应优先建议 quality gate、多帧一致性、补光或人工复核，而不是降低人脸匹配阈值。"""

_USER_PROMPT = """请分析这张校园门禁摄像头采样帧的环境质量。重点判断：是否阴天、低光、夜间、逆光、雨雾、曝光不足、过曝、画面模糊、面部区域是否可能可见。只返回 JSON。

JSON schema:
{
  "scene_tag": "indoor" | "semi_outdoor" | "outdoor" | "backlight" | "night" | "rain_fog" | "unknown",
  "lighting_quality": "good" | "overcast" | "low_light" | "backlight" | "unstable" | "unsafe",
  "face_visibility": "clear" | "acceptable" | "poor" | "unusable",
  "risk_level": "low" | "medium" | "high" | "critical",
  "profile": "normal" | "overcast" | "low_light" | "night" | "rain_fog" | "backlight" | "unsafe",
  "action_tags": ["keep_match_threshold", "lower_detector_threshold", "increase_liveness_threshold", "increase_frame_consensus", "enable_quality_gate", "enable_manual_review", "disable_auto_grant", "request_supplement_light"],
  "reason": "简短中文描述（≤200字）",
  "confidence": 0.0-1.0
}"""


def _bgr_to_data_url(bgr: np.ndarray, quality: int = 75) -> str:
    """Convert BGR ndarray → JPEG base64 data URL."""
    success, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise VLMError("Failed to encode frame as JPEG")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _call_api(api_key: str, base_url: str, model: str, payload: dict, timeout: float) -> dict:
    """Synchronous HTTP POST to OpenAI-compatible /v1/chat/completions."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    conn = http.client.HTTPSConnection(base_url, timeout=timeout)
    try:
        conn.request("POST", "/v1/chat/completions", body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        if resp.status != 200:
            raise VLMError(f"API HTTP {resp.status}: {raw[:300]}")
        return json.loads(raw)
    except VLMError:
        raise
    except Exception as e:
        raise VLMError(f"API call failed: {e}")
    finally:
        conn.close()


class VectorEngineProvider(VLMProvider):
    """VLM Provider backed by VectorEngine (OpenAI-compatible, GPT-4o vision).

    Also works with any OpenAI-compatible endpoint (DeepSeek, Qwen via
    compatible-mode, etc.) — just set ``base_url`` and ``model``.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        self._api_key = api_key or os.getenv("VECTORENGINE_API_KEY", "")
        self._base_url = base_url
        self._model = model
        self._timeout = timeout

    @property
    def api_key(self) -> str:
        return self._api_key

    @api_key.setter
    def api_key(self, value: str) -> None:
        self._api_key = value

    async def assess_scene(
        self,
        frame_bgr: np.ndarray,
        *,
        temp_dir: str | None = None,
    ) -> VLMSceneAssessment:
        """Call OpenAI-compatible vision API with a single camera frame."""
        if not self._api_key:
            raise VLMError("VECTORENGINE_API_KEY not set")

        data_url = _bgr_to_data_url(frame_bgr)

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _USER_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
        }

        data = await asyncio.to_thread(
            _call_api, self._api_key, self._base_url, self._model, payload, self._timeout,
        )

        try:
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content) if isinstance(content, str) else content
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise VLMError(f"API response parse failed: {e}\nRaw: {str(data)[:300]}")

        try:
            return VLMSceneAssessment(**parsed)
        except Exception as e:
            raise VLMError(
                f"VLMSceneAssessment validation failed: {e}\n"
                f"Parsed: {json.dumps(parsed, ensure_ascii=False)[:300]}"
            )
