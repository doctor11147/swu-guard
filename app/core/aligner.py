"""5-point similarity-transform alignment to the ArcFace 112x112 template.

Delegates to insightface.utils.face_align.norm_crop, which is the reference
implementation used by every InsightFace-trained recogniser (ArcFace, AdaFace,
EdgeFace, ...). Keeping a thin wrapper here lets us swap implementations later
without touching call sites.
"""
from __future__ import annotations

import numpy as np
from insightface.utils import face_align


def align_112(image_bgr: np.ndarray, kps: np.ndarray, output_size: int = 112) -> np.ndarray:
    """Warp face to canonical template.

    Args:
        image_bgr: original full-frame BGR uint8.
        kps: (5, 2) keypoints in original-image coordinates.
        output_size: must be a multiple of 112 or 128.

    Returns:
        BGR uint8, output_size x output_size x 3.
    """
    if kps.shape != (5, 2):
        raise ValueError(f"expected (5,2) keypoints, got {kps.shape}")
    return face_align.norm_crop(image_bgr, landmark=kps, image_size=output_size)
