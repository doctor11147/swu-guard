"""安全控制器测试 · 核心不变量。"""

from __future__ import annotations

import pytest

from app.schemas.adaptive import EnvironmentProfile
from app.services.adaptive_controller import (
    HARD_BOUNDS,
    PROFILE_TABLE,
    resolve_config,
    validate_decision,
)


def test_normal_profile_is_base():
    cfg = resolve_config("normal", "base")
    assert cfg.match_thresh >= 0.40
    assert cfg.spoof_thresh >= 0.85
    assert cfg.manual_review is False
    assert cfg.auto_grant_enabled is True


@pytest.mark.parametrize("profile", list(PROFILE_TABLE.keys()))
def test_all_profiles_within_hard_bounds(profile: EnvironmentProfile):
    cfg = resolve_config(profile, "test")
    assert HARD_BOUNDS["det_thresh"][0] <= cfg.det_thresh <= HARD_BOUNDS["det_thresh"][1]
    assert HARD_BOUNDS["spoof_thresh"][0] <= cfg.spoof_thresh <= HARD_BOUNDS["spoof_thresh"][1]
    assert HARD_BOUNDS["match_thresh"][0] <= cfg.match_thresh <= HARD_BOUNDS["match_thresh"][1]
    assert HARD_BOUNDS["quality_thresh"][0] <= cfg.quality_thresh <= HARD_BOUNDS["quality_thresh"][1]
    assert HARD_BOUNDS["consensus_frames"][0] <= cfg.consensus_frames <= HARD_BOUNDS["consensus_frames"][1]


def test_match_thresh_never_below_base():
    """match_thresh 在任何 profile 下不得低于 base (=0.40)。"""
    for profile in PROFILE_TABLE:
        cfg = resolve_config(profile, "test")
        assert cfg.match_thresh >= 0.40, f"{profile}: match_thresh={cfg.match_thresh} < 0.40"


def test_spoof_thresh_never_below_base():
    """spoof_thresh 在任何 profile 下不得低于 base (=0.85)。"""
    for profile in PROFILE_TABLE:
        cfg = resolve_config(profile, "test")
        assert cfg.spoof_thresh >= 0.85, f"{profile}: spoof_thresh={cfg.spoof_thresh} < 0.85"


def test_high_risk_forces_manual_review():
    """high / critical 风险必须启用 manual_review 或关闭 auto_grant。"""
    for risk in ("high", "critical"):
        d = validate_decision("night", risk, [], "high risk", 0.8)
        assert "enable_manual_review" in d.action_tags
        assert "disable_auto_grant" in d.action_tags


def test_validate_decision_always_keeps_match():
    """即使 VLM 忘了加，validate_decision 也要补上 keep_match_threshold。"""
    d = validate_decision("low_light", "medium", [], "test", 0.7)
    assert "keep_match_threshold" in d.action_tags


def test_night_profile_manual_review():
    cfg = resolve_config("night", "night test")
    assert cfg.manual_review is True
    assert cfg.auto_grant_enabled is False


def test_unsafe_profile_strictest():
    cfg = resolve_config("unsafe", "unsafe test")
    assert cfg.match_thresh >= 0.45
    assert cfg.spoof_thresh >= 0.92
    assert cfg.quality_thresh >= 0.80
    assert cfg.manual_review is True
    assert cfg.auto_grant_enabled is False
