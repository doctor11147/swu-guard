"""Dependency-free face quality estimate based on Laplacian sharpness.

The public repository intentionally ships no third-party quality-model code or
weights. A deployment may register another quality backend after separately
reviewing its source and model licenses.
"""
from __future__ import annotations

import cv2
import numpy as np

QUALITY_REGISTRATION_THRESHOLD = 0.30
QUALITY_LOW_THRESHOLD = 0.45
QUALITY_MATCH_PENALTY = 0.05


class FaceQualityAssessor:
    """Return a bounded sharpness score for an aligned BGR face crop."""

    available = True
    backend = "laplacian"

    def __init__(self, device: str = "cpu") -> None:
        self.device = device

    @staticmethod
    def score(face_bgr: np.ndarray) -> float:
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        bounded = max(10.0, min(variance, 200.0))
        return round((bounded - 10.0) / 190.0 * 8.0, 3)


_quality_assessor: FaceQualityAssessor | None = None


def get_quality_assessor(device: str = "cpu") -> FaceQualityAssessor:
    global _quality_assessor
    if _quality_assessor is None:
        _quality_assessor = FaceQualityAssessor(device=device)
    return _quality_assessor
