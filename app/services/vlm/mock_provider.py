"""Mock VLM Provider — rule-based fallback for offline demo & testing.

Maps luma_mean (extracted from the frame) to a plausible VLMSceneAssessment
without any network call.  This is the default provider when no API key is set.
"""

from __future__ import annotations

import numpy as np

from app.schemas.adaptive import VLMSceneAssessment
from app.services.illumination_probe import analyze_frame_quality
from app.services.vlm.base import VLMProvider


class MockProvider(VLMProvider):
    """Deterministic mock — converts luma_mean into a scene assessment.

    Mapping:
      luma_mean >= 100 → normal
      60  <= luma_mean < 100 → overcast
      35  <= luma_mean < 60  → low_light
      luma_mean < 35  → night
    """

    async def assess_scene(
        self,
        frame_bgr: np.ndarray,
        *,
        temp_dir: str | None = None,
    ) -> VLMSceneAssessment:
        """Infer scene from frame brightness.  Always returns valid JSON."""
        q = analyze_frame_quality(frame_bgr)
        lm = q.luma_mean
        blur = q.blur_score
        over = q.over_exposed_ratio

        # ── 确定 profile ──
        if lm >= 100:
            profile = "normal"
            risk = "low"
            scene_tag = "outdoor"
            lighting = "good"
            visibility = "clear"
        elif lm >= 60:
            profile = "overcast"
            risk = "medium"
            scene_tag = "semi_outdoor"
            lighting = "overcast"
            visibility = "acceptable"
        elif lm >= 35:
            profile = "low_light"
            risk = "high" if blur < 80 else "medium"
            scene_tag = "outdoor"
            lighting = "low_light"
            visibility = "acceptable" if blur >= 80 else "poor"
        else:
            profile = "night"
            risk = "high"
            scene_tag = "night"
            lighting = "low_light"
            visibility = "poor" if blur < 60 else "acceptable"

        # 过曝 → backlight
        if over > 0.25:
            profile = "backlight"
            risk = "high"
            scene_tag = "backlight"
            lighting = "backlight"
            visibility = "poor"

        # ── action_tags ──
        tags = ["keep_match_threshold"]
        if profile in ("low_light", "night", "backlight"):
            tags.append("lower_detector_threshold")
            tags.append("increase_liveness_threshold")
            tags.append("increase_frame_consensus")
            tags.append("enable_quality_gate")
        if profile in ("night", "backlight"):
            tags.extend(["enable_manual_review", "disable_auto_grant"])

        return VLMSceneAssessment(
            scene_tag=scene_tag,
            lighting_quality=lighting,
            face_visibility=visibility,
            risk_level=risk,
            profile=profile,
            action_tags=tags,
            reason=f"Mock: luma={lm:.1f} blur={blur:.1f} over={over:.2f}",
            confidence=0.65,
        )
