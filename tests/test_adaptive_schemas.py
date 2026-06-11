"""自适应 schema 枚举与数据校验测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.adaptive import (
    AdaptiveDecision,
    CameraQualitySnapshot,
    EvaluateRequest,
    RuntimeRecognitionConfig,
    VLMSceneAssessment,
)


def test_vlm_scene_assessment_valid():
    a = VLMSceneAssessment(
        scene_tag="outdoor",
        lighting_quality="low_light",
        face_visibility="acceptable",
        risk_level="medium",
        profile="low_light",
        action_tags=["keep_match_threshold", "increase_liveness_threshold"],
        reason="傍晚逆光，轮廓侧光，面部区域偏暗",
        confidence=0.82,
    )
    assert a.profile == "low_light"
    assert a.risk_level == "medium"


def test_vlm_scene_assessment_invalid_profile():
    with pytest.raises(ValidationError):
        VLMSceneAssessment(
            scene_tag="outdoor",
            lighting_quality="good",
            face_visibility="clear",
            risk_level="low",
            profile="invalid_profile",  # type: ignore[arg-type]
            action_tags=[],
            reason="",
            confidence=0.9,
        )


def test_camera_quality_snapshot():
    q = CameraQualitySnapshot(
        luma_mean=45.2, luma_std=18.3, blur_score=95.0,
        under_exposed_ratio=0.40, over_exposed_ratio=0.05,
    )
    assert q.luma_mean == 45.2
    assert q.blur_score == 95.0


def test_runtime_config_bounds():
    cfg = RuntimeRecognitionConfig(
        profile="normal",
        det_thresh=0.50, spoof_thresh=0.85, match_thresh=0.40,
        quality_thresh=0.50, consensus_frames=3,
        manual_review=False, auto_grant_enabled=True,
        reason="base",
    )
    assert cfg.match_thresh >= 0.40


def test_adaptive_decision_enums():
    d = AdaptiveDecision(
        profile="low_light",
        risk_level="medium",
        should_apply=True,
        action_tags=["keep_match_threshold"],
        reason="低光照场景",
        expires_in_minutes=30,
        confidence=0.78,
    )
    assert d.expires_in_minutes >= 5
    assert 0.0 <= d.confidence <= 1.0


def test_evaluate_request_defaults():
    r = EvaluateRequest()
    assert r.gate_id is None
    assert r.use_weather is False
