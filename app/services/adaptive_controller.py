"""Safety Validator — maps EnvironmentProfile → RuntimeRecognitionConfig.

Core invariant
--------------
match_thresh and spoof_thresh MUST NEVER fall below their base values.
High-risk / critical profiles MUST require manual_review or disable auto_grant.
The VLM/LLM may only suggest *actions* — this module is the sole authority that
maps actions to concrete numeric parameters within hard bounds.
"""

from __future__ import annotations

from app.schemas.adaptive import (
    ActionTag,
    AdaptiveDecision,
    EnvironmentProfile,
    RiskLevel,
    RuntimeRecognitionConfig,
)

# ── 基准值（不可突破的下界）──────────────────────────────────────────

BASE = {
    "det_thresh": 0.50,
    "spoof_thresh": 0.85,
    "match_thresh": 0.40,
    "quality_thresh": 0.50,
    "consensus_frames": 3,
}

# ── Profile → 参数映射 ───────────────────────────────────────────────

PROFILE_TABLE: dict[EnvironmentProfile, dict] = {
    "normal": {
        "det_thresh": 0.50, "spoof_thresh": 0.85, "match_thresh": 0.40,
        "quality_thresh": 0.50, "consensus_frames": 3,
        "manual_review": False, "auto_grant_enabled": True,
    },
    "overcast": {
        "det_thresh": 0.45, "spoof_thresh": 0.85, "match_thresh": 0.40,
        "quality_thresh": 0.55, "consensus_frames": 4,
        "manual_review": False, "auto_grant_enabled": True,
    },
    "low_light": {
        "det_thresh": 0.45, "spoof_thresh": 0.88, "match_thresh": 0.41,
        "quality_thresh": 0.65, "consensus_frames": 5,
        "manual_review": False, "auto_grant_enabled": True,
    },
    "night": {
        "det_thresh": 0.40, "spoof_thresh": 0.90, "match_thresh": 0.42,
        "quality_thresh": 0.70, "consensus_frames": 5,
        "manual_review": True, "auto_grant_enabled": False,
    },
    "rain_fog": {
        "det_thresh": 0.42, "spoof_thresh": 0.90, "match_thresh": 0.42,
        "quality_thresh": 0.70, "consensus_frames": 5,
        "manual_review": True, "auto_grant_enabled": False,
    },
    "backlight": {
        "det_thresh": 0.42, "spoof_thresh": 0.90, "match_thresh": 0.42,
        "quality_thresh": 0.72, "consensus_frames": 5,
        "manual_review": True, "auto_grant_enabled": False,
    },
    "unsafe": {
        "det_thresh": 0.50, "spoof_thresh": 0.92, "match_thresh": 0.45,
        "quality_thresh": 0.80, "consensus_frames": 5,
        "manual_review": True, "auto_grant_enabled": False,
    },
}

# ── 硬边界 ───────────────────────────────────────────────────────────

HARD_BOUNDS = {
    "det_thresh": (0.35, 0.70),
    "spoof_thresh": (BASE["spoof_thresh"], 0.95),
    "match_thresh": (BASE["match_thresh"], 0.50),
    "quality_thresh": (0.40, 0.85),
    "consensus_frames": (3, 7),
}


def _clamp(key: str, value: float | int) -> float | int:
    lo, hi = HARD_BOUNDS[key]
    return max(lo, min(hi, value))


def resolve_config(
    profile: EnvironmentProfile,
    reason: str,
    *,
    action_tags: list[ActionTag] | None = None,
) -> RuntimeRecognitionConfig:
    """Map a validated profile into concrete recognition parameters.

    VLM/rule action_tags are informational at this layer — the profile table
    is the single source of truth for numeric mapping.
    """
    cfg = PROFILE_TABLE.get(profile, PROFILE_TABLE["normal"])
    return RuntimeRecognitionConfig(
        profile=profile,
        det_thresh=_clamp("det_thresh", cfg["det_thresh"]),
        spoof_thresh=_clamp("spoof_thresh", cfg["spoof_thresh"]),
        match_thresh=_clamp("match_thresh", cfg["match_thresh"]),
        quality_thresh=_clamp("quality_thresh", cfg["quality_thresh"]),
        consensus_frames=int(_clamp("consensus_frames", cfg["consensus_frames"])),
        manual_review=bool(cfg.get("manual_review", False)),
        auto_grant_enabled=bool(cfg.get("auto_grant_enabled", True)),
        reason=reason,
    )


def validate_decision(
    profile: EnvironmentProfile,
    risk_level: RiskLevel,
    action_tags: list[ActionTag],
    reason: str,
    confidence: float,
) -> AdaptiveDecision:
    """Safety gate: never lower match/spoof below base, force manual review on high risk.

    Returns an AdaptiveDecision that downstream code can trust to be within bounds.
    """
    # 高风险 / 紧急 → 强制人工复核
    if risk_level in ("high", "critical"):
        if "enable_manual_review" not in action_tags:
            action_tags = list(action_tags) + ["enable_manual_review"]
        if "disable_auto_grant" not in action_tags:
            action_tags = list(action_tags) + ["disable_auto_grant"]

    # 绝不允许放宽 match
    if "keep_match_threshold" not in action_tags:
        action_tags = list(action_tags) + ["keep_match_threshold"]

    return AdaptiveDecision(
        profile=profile,
        risk_level=risk_level,
        should_apply=True,
        action_tags=list(set(action_tags)),
        reason=reason,
        expires_in_minutes=60,
        confidence=confidence,
    )
