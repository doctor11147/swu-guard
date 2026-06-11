"""环境感知自适应控制 Pydantic v2 数据契约。

English summary
---------------
Structured schemas for the VLM-prior environment-aware adaptive gate controller.
VLM/LLM may only output profiles and action tags; numeric thresholds are derived
by the SafetyValidator via a hardcoded profile table with strict upper/lower bounds.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ── 枚举类型 ──────────────────────────────────────────────────────────

EnvironmentProfile = Literal[
    "normal",
    "overcast",
    "low_light",
    "night",
    "rain_fog",
    "backlight",
    "unsafe",
]

RiskLevel = Literal["low", "medium", "high", "critical"]

ActionTag = Literal[
    "lower_detector_threshold",
    "increase_liveness_threshold",
    "keep_match_threshold",
    "increase_match_threshold",
    "increase_frame_consensus",
    "enable_quality_gate",
    "enable_manual_review",
    "request_supplement_light",
    "disable_auto_grant",
]

AdaptiveMode = Literal["off", "rule_only", "vlm", "vlm_weather"]

# ── VLM 场景评估 ─────────────────────────────────────────────────────

class VLMSceneAssessment(BaseModel):
    """Structured scene observation returned by a VLM provider.

    The VLM must ONLY describe the environment — it must NOT identify persons,
    output biometric conclusions, or suggest numeric thresholds.
    """

    scene_tag: Literal[
        "indoor", "semi_outdoor", "outdoor",
        "backlight", "night", "rain_fog", "unknown",
    ]
    lighting_quality: Literal[
        "good", "overcast", "low_light", "backlight", "unstable", "unsafe",
    ]
    face_visibility: Literal["clear", "acceptable", "poor", "unusable"]
    risk_level: RiskLevel
    profile: EnvironmentProfile
    action_tags: list[ActionTag]
    reason: str = Field(max_length=800)
    confidence: float = Field(ge=0.0, le=1.0)


# ── 摄像头质量探针 ───────────────────────────────────────────────────

class CameraQualitySnapshot(BaseModel):
    """Low-level frame quality metrics computed by illumination_probe."""

    luma_mean: float
    luma_std: float
    blur_score: float
    under_exposed_ratio: float
    over_exposed_ratio: float


# ── 近期识别统计 ─────────────────────────────────────────────────────

class RecentRecognitionStats(BaseModel):
    """Rolling window stats from access_logs (default 15 min)."""

    window_minutes: int
    total_events: int
    reject_rate: float
    low_quality_rate: float
    spoof_reject_rate: float
    avg_similarity: float | None = None


# ── 天气佐证 ─────────────────────────────────────────────────────────

class WeatherEvidence(BaseModel):
    """Lightweight weather snapshot (Open-Meteo).  Never the primary signal."""

    provider: str = "open_meteo"
    cloud_pct: float | None = None
    visibility_km: float | None = None
    precipitation_mm: float | None = None
    irradiance: float | None = None
    humidity_pct: float | None = None
    is_day: bool | None = None
    raw: dict | None = None


# ── 自适应决策与运行时配置 ───────────────────────────────────────────

class AdaptiveDecision(BaseModel):
    """Final validated decision after safety controller."""

    profile: EnvironmentProfile
    risk_level: RiskLevel
    should_apply: bool
    action_tags: list[ActionTag]
    reason: str = Field(max_length=800)
    expires_in_minutes: int = Field(ge=5, le=60)
    confidence: float = Field(ge=0.0, le=1.0)


class RuntimeRecognitionConfig(BaseModel):
    """Resolved recognition parameters after safety validation.

    These are the actual values the recognition pipeline reads at runtime.
    """

    profile: EnvironmentProfile
    det_thresh: float
    spoof_thresh: float
    match_thresh: float
    quality_thresh: float
    consensus_frames: int
    manual_review: bool
    auto_grant_enabled: bool
    reason: str


# ── API 响应模型 ─────────────────────────────────────────────────────

class AdaptiveStateOut(BaseModel):
    """GET /api/adaptive/state response."""

    enabled: bool
    mode: AdaptiveMode
    profile: EnvironmentProfile
    risk_level: RiskLevel
    runtime_config: RuntimeRecognitionConfig | None = None
    last_reason: str | None = None
    expires_at: datetime | None = None
    last_updated_at: datetime | None = None


class EvaluateRequest(BaseModel):
    """POST /api/adaptive/evaluate request."""

    gate_id: int | None = None
    use_weather: bool = False
    image_base64: str | None = None  # 可选：摄像头抓帧（JPEG base64），不传则用灰帧占位


class EvaluateResponse(BaseModel):
    """POST /api/adaptive/evaluate response."""

    snapshot_id: int | None = None
    decision: AdaptiveDecision
    validated_config: RuntimeRecognitionConfig
    applied: bool = False


class AdaptiveConfigUpdate(BaseModel):
    """PUT /api/adaptive/config request."""

    enabled: bool | None = None
    mode: AdaptiveMode | None = None
    vlm_provider: Literal["deepseek", "mock"] | None = None
    vlm_interval_seconds: int | None = Field(None, ge=0, le=3600)
    weather_enabled: bool | None = None
