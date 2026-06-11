"""摄像头质量探针测试。"""

from __future__ import annotations

import numpy as np

from app.schemas.adaptive import CameraQualitySnapshot
from app.services.illumination_probe import analyze_frame_quality, quality_flags


def _bgr(w: int, h: int, value: int) -> np.ndarray:
    return np.full((h, w, 3), value, dtype=np.uint8)


def test_black_frame():
    bgr = _bgr(200, 200, 5)
    q = analyze_frame_quality(bgr)
    assert q.luma_mean < 10
    assert q.under_exposed_ratio > 0.9
    assert q.over_exposed_ratio < 0.01


def test_white_frame():
    bgr = _bgr(200, 200, 245)
    q = analyze_frame_quality(bgr)
    assert q.luma_mean > 230
    assert q.over_exposed_ratio > 0.8


def test_normal_frame():
    bgr = _bgr(200, 200, 140)
    q = analyze_frame_quality(bgr)
    assert 130 < q.luma_mean < 150
    assert q.under_exposed_ratio < 0.01
    assert q.over_exposed_ratio < 0.01


def test_low_light_flags():
    q = CameraQualitySnapshot(
        luma_mean=45.0, luma_std=10.0, blur_score=100.0,
        under_exposed_ratio=0.40, over_exposed_ratio=0.02,
    )
    flags = quality_flags(q)
    assert flags["low_light"] is True
    assert flags["under_exposed"] is True
    assert flags["blurry"] is False
    assert flags["over_exposed"] is False


def test_blurry_flags():
    q = CameraQualitySnapshot(
        luma_mean=140.0, luma_std=20.0, blur_score=40.0,
        under_exposed_ratio=0.05, over_exposed_ratio=0.05,
    )
    flags = quality_flags(q)
    assert flags["blurry"] is True


def test_none_input():
    q = analyze_frame_quality(None)  # type: ignore[arg-type]
    assert q.luma_mean == 0.0
    assert q.blur_score == 0.0
