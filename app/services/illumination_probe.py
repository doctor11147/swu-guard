"""Camera quality probe — no deep learning, pure Laplacian + luminance stats.

English summary
---------------
Computes luma Mean/std, blur (Laplacian variance), and under/over exposure ratios
from a single BGR frame.  Threshold references are kept here as module defaults
and can be overridden via system_configs.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.schemas.adaptive import CameraQualitySnapshot

# 默认判定阈值（可由 system_configs 覆盖）
LUMA_LOW_THRESHOLD = 60        # luma_mean < 60 → low_light 倾向
BLUR_LOW_THRESHOLD = 80        # laplacian var < 80 → blurry
UNDER_EXPOSED_RATIO = 0.35     # > 35% 像素在暗区 → under_exposed
OVER_EXPOSED_RATIO = 0.25      # > 25% 像素在高亮区 → over/backlight
UNDER_EXPOSED_PX = 40          # 像素值 ≤ 40 视为欠曝
OVER_EXPOSED_PX = 220          # 像素值 ≥ 220 视为过曝


def analyze_frame_quality(bgr: np.ndarray) -> CameraQualitySnapshot:
    """Analyze illumination and sharpness of one BGR frame.

    Args:
        bgr: BGR image as uint8 ndarray (H, W, 3).

    Returns:
        CameraQualitySnapshot with luma mean, blur score, and exposure ratios.
    """
    if bgr is None or bgr.size == 0:
        return CameraQualitySnapshot(
            luma_mean=0.0, luma_std=0.0, blur_score=0.0,
            under_exposed_ratio=0.0, over_exposed_ratio=0.0,
        )

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)

    luma_mean = float(gray.mean())
    luma_std = float(gray.std())

    # Laplacian 方差作为模糊度量（越大越锐利）
    blur_score = float(cv2.Laplacian(gray.astype(np.uint8), cv2.CV_64F).var())

    total = gray.size
    under = float((gray <= UNDER_EXPOSED_PX).sum()) / total
    over = float((gray >= OVER_EXPOSED_PX).sum()) / total

    return CameraQualitySnapshot(
        luma_mean=luma_mean,
        luma_std=luma_std,
        blur_score=blur_score,
        under_exposed_ratio=under,
        over_exposed_ratio=over,
    )


def quality_flags(snap: CameraQualitySnapshot) -> dict[str, bool]:
    """Return boolean flags summarising common quality issues."""
    return {
        "low_light": snap.luma_mean < LUMA_LOW_THRESHOLD,
        "blurry": snap.blur_score < BLUR_LOW_THRESHOLD,
        "under_exposed": snap.under_exposed_ratio > UNDER_EXPOSED_RATIO,
        "over_exposed": snap.over_exposed_ratio > OVER_EXPOSED_RATIO,
    }
