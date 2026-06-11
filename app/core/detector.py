"""SCRFD face detector via insightface.app.FaceAnalysis.

We only consume the 'detection' module (5-keypoint output). The bundle is
auto-downloaded into `insightface_root/models/<bundle>/` on first use.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
from insightface.app import FaceAnalysis


@dataclass
class Detection:
    bbox: np.ndarray  # (4,) float32, [x1, y1, x2, y2] in original image coords
    score: float
    kps: np.ndarray   # (5, 2) float32, [left_eye, right_eye, nose, left_mouth, right_mouth]


class SCRFDDetector:
    def __init__(
        self,
        bundle: str = "buffalo_sc",
        root: str | Path = "~/.insightface",
        det_size: tuple[int, int] = (640, 640),
        det_thresh: float = 0.5,
        ctx_id: int = -1,
    ):
        # allowed_modules limits to detection so we don't load the recognition ONNX
        # bundled inside buffalo_*; this keeps memory and startup time low.
        self._app = FaceAnalysis(
            name=bundle,
            root=str(Path(root).expanduser()),
            allowed_modules=["detection"],
        )
        self._app.prepare(ctx_id=ctx_id, det_size=tuple(det_size), det_thresh=det_thresh)

    def detect(self, image_bgr: np.ndarray, max_num: int = 0) -> List[Detection]:
        """Run detection on a BGR uint8 image.

        Args:
            image_bgr: H x W x 3 uint8 BGR (cv2 convention).
            max_num: 0 for unlimited; otherwise top-N by area.

        Returns:
            List of Detection sorted by detection score descending.
        """
        faces = self._app.get(image_bgr, max_num=max_num)
        out: List[Detection] = []
        for f in faces:
            if f.kps is None:
                continue
            out.append(Detection(
                bbox=np.asarray(f.bbox, dtype=np.float32),
                score=float(f.det_score),
                kps=np.asarray(f.kps, dtype=np.float32),
            ))
        out.sort(key=lambda d: d.score, reverse=True)
        return out

    def detect_largest(self, image_bgr: np.ndarray) -> Detection | None:
        """Convenience: return the highest-scoring detection or None."""
        dets = self.detect(image_bgr, max_num=1)
        return dets[0] if dets else None
