"""Environment-aware adaptive gate controller orchestrator.

English summary
---------------
Periodically evaluates the current scene (camera quality → rule-based or VLM
profile → safety validator) and caches the resulting RuntimeRecognitionConfig.
The recognition pipeline calls `get_runtime_config()` to read the latest
validated config; VLM calls are async, non-blocking, and can degrade gracefully.

Modes (set via system_configs key ``adaptive.mode``):
  - ``off``         → always returns normal base config
  - ``rule_only``    → camera quality probe + recent stats → rule-based profile
  - ``vlm``          → VLM provider (DeepSeek / mock) + validator
  - ``vlm_weather``  → VLM + weather client; weather failure → vlm fallback
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Protocol

import numpy as np

from app.schemas.adaptive import (
    ActionTag,
    AdaptiveDecision,
    AdaptiveMode,
    CameraQualitySnapshot,
    EnvironmentProfile,
    RecentRecognitionStats,
    RiskLevel,
    RuntimeRecognitionConfig,
    WeatherEvidence,
)

# ── 轻量协程级缓存（避免频繁 DB 查询 & VLM 调用）─────────────────────

_cache: RuntimeRecognitionConfig | None = None
_cache_ts: float = 0.0
_cache_ttl: float = 60.0  # 60 秒内复用


def _now() -> float:
    return time.monotonic()


def get_cached_config() -> RuntimeRecognitionConfig | None:
    if _cache is not None and (_now() - _cache_ts) < _cache_ttl:
        return _cache
    return None


def set_cached_config(cfg: RuntimeRecognitionConfig) -> None:
    global _cache, _cache_ts
    _cache = cfg
    _cache_ts = _now()


# ── Provider protocol ─────────────────────────────────────────────────

class VLMProviderProto(Protocol):
    """Structural interface for VLM providers — avoids hard import."""

    async def assess_scene(self, frame_bgr: np.ndarray, *, temp_dir: Path) -> object:
        ...


class WeatherClientProto(Protocol):
    """Structural interface for weather clients."""

    async def fetch(self, lat: float, lon: float) -> object:
        ...


# ── Rule-based profile from quality snapshot ─────────────────────────

def _infer_profile_from_quality(q: CameraQualitySnapshot) -> EnvironmentProfile:
    """Heuristic: luma + blur + exposure ratios → profile.

    These thresholds mirror ``illumination_probe`` module defaults.
    """
    if q.luma_mean < 35:
        return "night"
    if q.luma_mean < 60:
        return "low_light"
    if q.over_exposed_ratio > 0.25:
        return "backlight"
    if q.luma_mean < 100:
        return "overcast"
    return "normal"


def _infer_risk_from_quality(q: CameraQualitySnapshot) -> RiskLevel:
    if q.luma_mean < 25 or q.over_exposed_ratio > 0.50:
        return "critical"
    if q.luma_mean < 50 or q.blur_score < 80:
        return "high"
    if q.luma_mean < 80:
        return "medium"
    return "low"


def _action_tags_for_profile(profile: EnvironmentProfile) -> list[ActionTag]:
    tags: list[ActionTag] = []
    if profile in ("low_light", "night", "backlight", "unsafe"):
        tags.extend(["lower_detector_threshold", "keep_match_threshold"])
    if profile in ("night", "rain_fog", "backlight", "unsafe"):
        tags.extend(["increase_liveness_threshold", "increase_frame_consensus", "enable_quality_gate"])
    if profile in ("night", "rain_fog", "unsafe"):
        tags.extend(["enable_manual_review", "disable_auto_grant"])
    return tags


# ── 天气佐证：弱证据，只升不降 ──────────────────────────────────────

# profile 严重程度排序（低→高），天气只能向右推进
_SEVERITY: dict[EnvironmentProfile, int] = {
    "normal": 0, "overcast": 1, "low_light": 2,
    "night": 3, "rain_fog": 4, "backlight": 5, "unsafe": 6,
}


def _weather_corroborate(
    profile: EnvironmentProfile,
    risk: RiskLevel,
    action_tags: list[ActionTag],
    wx: WeatherEvidence,
) -> tuple[EnvironmentProfile, RiskLevel, list[ActionTag], str]:
    """天气弱佐证：用气象客观数据修正 VLM 判断。

    原则：
    - 天气只能升级 profile/risk，绝不降级（VLM 是主信号）
    - 仅使用光照相关字段：is_day / irradiance（太阳辐照度）/ cloud_pct / visibility
    - 降水/云量作辅助说明，不独立改变 profile
    """
    notes: list[str] = []
    original = profile

    # 1. 夜间 → 最低 low_light
    if wx.is_day is False:
        if _SEVERITY[profile] < _SEVERITY["low_light"]:
            profile = "low_light"
            notes.append("气象显示当前为夜间")

    # 2. 太阳辐照度极低 → 等效夜间/阴天（即使 VLM 看到室内灯光认为 normal）
    if wx.irradiance is not None and wx.irradiance < 80:
        if _SEVERITY[profile] < _SEVERITY["overcast"]:
            profile = "overcast"
            notes.append(f"太阳辐照度极低({wx.irradiance:.0f}W/m²)")

    # 3. 低辐照 + 高云量 → 升级为 low_light
    if wx.irradiance is not None and wx.cloud_pct is not None:
        if wx.irradiance < 200 and wx.cloud_pct > 70:
            if _SEVERITY[profile] < _SEVERITY["low_light"]:
                profile = "low_light"
                notes.append(f"低辐照({wx.irradiance:.0f}W/m²)+高云量({wx.cloud_pct:.0f}%)")

    # 4. 降雨 → rain_fog
    if wx.precipitation_mm is not None and wx.precipitation_mm > 0:
        if _SEVERITY[profile] < _SEVERITY["rain_fog"]:
            profile = "rain_fog"
            notes.append(f"当前降水 {wx.precipitation_mm:.1f}mm")

    # 5. 低能见度 → rain_fog / unsafe
    if wx.visibility_km is not None and wx.visibility_km < 1.0:
        if _SEVERITY[profile] < _SEVERITY["rain_fog"]:
            profile = "rain_fog"
            notes.append(f"低能见度({wx.visibility_km:.2f}km)")

    # 6. profile 升级后同步 risk + action_tags
    if profile != original:
        new_risk = _infer_risk_from_profile(profile)
        if _SEVERITY.get(profile, 0) >= _SEVERITY.get("night", 3):
            new_risk = "high"
        risk = max(risk, new_risk, key=lambda r: {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(r, 0))  # type: ignore[arg-type]
        action_tags = list(set(action_tags + _action_tags_for_profile(profile)))

    # 构造天气说明（用 is not None 避免 0.0 被 falsy 吞掉）
    parts = [
        f"cloud={wx.cloud_pct}%" if wx.cloud_pct is not None else "",
        f"irrad={wx.irradiance:.0f}W/m²" if wx.irradiance is not None else "",
        "day" if wx.is_day is True else "night" if wx.is_day is False else "",
        f"rain={wx.precipitation_mm:.1f}mm" if wx.precipitation_mm is not None else "",
        f"vis={wx.visibility_km:.2f}km" if wx.visibility_km is not None else "",
    ]
    wx_summary = "weather: " + " ".join(p for p in parts if p)
    if notes:
        wx_summary += " | ⚡" + "; ".join(notes)

    return profile, risk, action_tags, wx_summary


def _infer_risk_from_profile(profile: EnvironmentProfile) -> RiskLevel:
    """按 profile 严重度推断风险等级。"""
    mapping: dict[EnvironmentProfile, RiskLevel] = {
        "normal": "low", "overcast": "medium", "low_light": "medium",
        "night": "high", "rain_fog": "high", "backlight": "high", "unsafe": "critical",
    }
    return mapping.get(profile, "low")


# ── 主入口 ───────────────────────────────────────────────────────────

async def evaluate_and_apply(
    *,
    mode: AdaptiveMode = "rule_only",
    gate_id: int | None = None,
    frame_bgr: np.ndarray | None = None,
    provider: VLMProviderProto | None = None,
    weather: WeatherClientProto | None = None,
    db_session=None,  # AsyncSession | None, 延迟导入避免循环
    lat: float = 29.82,
    lon: float = 106.43,
    temp_dir: Path | None = None,
) -> RuntimeRecognitionConfig:
    """Run one evaluation cycle and return the resolved config.

    The returned config is also cached for downstream `get_runtime_config()` calls.
    """
    from app.services import illumination_probe, adaptive_controller

    # 1. mode=off → normal base
    if mode == "off":
        cfg = adaptive_controller.resolve_config("normal", "adaptive mode is off")
        set_cached_config(cfg)
        return cfg

    # 2. 摄像头质量探针
    quality: CameraQualitySnapshot | None = None
    if frame_bgr is not None and frame_bgr.size > 0:
        quality = illumination_probe.analyze_frame_quality(frame_bgr)

    # 3. 近期统计
    stats = RecentRecognitionStats(
        window_minutes=15, total_events=0,
        reject_rate=0.0, low_quality_rate=0.0, spoof_reject_rate=0.0,
        avg_similarity=None,
    )
    if db_session is not None:
        try:
            from app.services.recent_stats_service import get_recent_stats
            stats = await get_recent_stats(db_session)
        except Exception:
            pass  # 统计失败不阻塞

    # 4. 按模式决策
    profile: EnvironmentProfile = "normal"
    risk: RiskLevel = "low"
    action_tags: list[ActionTag] = []
    reason: str = ""
    confidence: float = 0.5
    weather_ev: WeatherEvidence | None = None

    if mode == "rule_only":
        # 纯规则：质量 → profile → controller
        if quality is not None:
            profile = _infer_profile_from_quality(quality)
            risk = _infer_risk_from_quality(quality)
            action_tags = _action_tags_for_profile(profile)
            reason = (
                f"Rule-only: luma={quality.luma_mean:.1f} blur={quality.blur_score:.1f}"
                f" under={quality.under_exposed_ratio:.2f} over={quality.over_exposed_ratio:.2f}"
                f" | recent_rejects={stats.reject_rate:.2f}"
            )
        else:
            reason = "Rule-only: no frame available, default to normal"
        confidence = 0.6

    elif mode == "vlm":
        if provider is not None and frame_bgr is not None:
            try:
                vlm_result = await asyncio.wait_for(
                    provider.assess_scene(frame_bgr, temp_dir=temp_dir or Path("/tmp")),
                    timeout=15.0,
                )
                # 从 VLM 结果提取结构化字段
                if hasattr(vlm_result, "profile"):
                    profile = getattr(vlm_result, "profile", "normal")  # type: ignore[assignment]
                    risk = getattr(vlm_result, "risk_level", "low")  # type: ignore[assignment]
                    action_tags = getattr(vlm_result, "action_tags", [])
                    reason = getattr(vlm_result, "reason", "VLM assessment")
                    confidence = float(getattr(vlm_result, "confidence", 0.5))
                else:
                    reason = "VLM returned unrecognised structure; fallback to quality"
            except Exception:
                # VLM 失败 → 降级到 rule_only
                if quality is not None:
                    profile = _infer_profile_from_quality(quality)
                    risk = _infer_risk_from_quality(quality)
                    action_tags = _action_tags_for_profile(profile)
                    reason = f"VLM failed; fallback to rule: luma={quality.luma_mean:.1f}"
                else:
                    reason = "VLM failed; no quality snapshot; falling back to normal"
                confidence = 0.3
        else:
            # 无 provider 或 frame → 降级
            if quality is not None:
                profile = _infer_profile_from_quality(quality)
                risk = _infer_risk_from_quality(quality)
                action_tags = _action_tags_for_profile(profile)
                reason = f"No VLM provider; rule-only: luma={quality.luma_mean:.1f}"
            confidence = 0.3

    elif mode == "vlm_weather":
        # VLM 为主，weather 为弱佐证（只升不降）
        if provider is not None and frame_bgr is not None:
            try:
                vlm_result = await asyncio.wait_for(
                    provider.assess_scene(frame_bgr, temp_dir=temp_dir or Path("/tmp")),
                    timeout=15.0,
                )
                profile = getattr(vlm_result, "profile", "normal")  # type: ignore[assignment]
                risk = getattr(vlm_result, "risk_level", "low")  # type: ignore[assignment]
                action_tags = getattr(vlm_result, "action_tags", [])
                reason = getattr(vlm_result, "reason", "VLM assessment")
                confidence = float(getattr(vlm_result, "confidence", 0.5))
            except Exception:
                if quality is not None:
                    profile = _infer_profile_from_quality(quality)
                    risk = _infer_risk_from_quality(quality)
                    action_tags = _action_tags_for_profile(profile)
                    reason = f"VLM+weather VLM failed; fallback: luma={quality.luma_mean:.1f}"
                else:
                    reason = "VLM+weather both failed; falling back to normal"
                confidence = 0.2

        # 天气佐证：只升级不降级，只追加不覆盖
        # 不要用 asyncio.wait_for 包裹——WeatherClient.fetch 内部用了
        # asyncio.to_thread，两者组合会触发 CancelledError。
        if weather is not None:
            try:
                raw = await weather.fetch(lat, lon)
                if isinstance(raw, WeatherEvidence) and raw.provider != "open_meteo_unavailable":
                    weather_ev = raw
                    profile, risk, action_tags, wx_note = _weather_corroborate(
                        profile, risk, action_tags, weather_ev,
                    )
                    reason += f" | {wx_note}"
                else:
                    reason += " | weather: unavailable"
            except Exception:
                reason += " | weather: unavailable"
        else:
            reason += " | weather: disabled"

    # 5. Safety Validator
    decision: AdaptiveDecision = adaptive_controller.validate_decision(
        profile=profile,
        risk_level=risk,
        action_tags=action_tags,
        reason=reason,
        confidence=confidence,
    )

    # 6. 解析为运行参数
    cfg = adaptive_controller.resolve_config(
        profile=decision.profile,
        reason=decision.reason,
        action_tags=decision.action_tags,
    )

    set_cached_config(cfg)
    return cfg


async def get_runtime_config(
    *,
    mode: AdaptiveMode = "rule_only",
    gate_id: int | None = None,
    frame_bgr: np.ndarray | None = None,
    provider: VLMProviderProto | None = None,
    weather: WeatherClientProto | None = None,
    db_session=None,
) -> RuntimeRecognitionConfig:
    """Return the current runtime config, re-evaluating if cache expired.

    This is the single entry-point the recognition pipeline uses.
    It evaluates every ~60 s; otherwise returns cached.
    """
    cached = get_cached_config()
    if cached is not None:
        return cached

    return await evaluate_and_apply(
        mode=mode,
        gate_id=gate_id,
        frame_bgr=frame_bgr,
        provider=provider,
        weather=weather,
        db_session=db_session,
    )
