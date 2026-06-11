"""End-to-end inference orchestrator: detect -> (anti-spoof) -> align -> embed.

This module composes the four primitives without itself owning any I/O. The
result objects are plain dataclasses; persistence (FAISS, DB, files) is done
by `app.store` and `app.api`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Optional

import numpy as np

from .aligner import align_112
from .anti_spoof import SpoofResult
from .detector import Detection
from .registry import (
    AntiSpoof,
    Detector,
    Embedder,
    create_anti_spoof,
    create_detector,
    create_embedder,
)


@dataclass
class FaceRecord:
    detection: Detection
    aligned_112: np.ndarray         # (112, 112, 3) uint8 BGR
    embedding: Optional[np.ndarray] = None   # (512,) float32 L2-normed
    spoof: Optional[SpoofResult] = None      # None if anti_spoof disabled
    skipped_reason: Optional[str] = None     # set when embedding is skipped (e.g., spoof)


@dataclass
class FrameResult:
    faces: list[FaceRecord] = field(default_factory=list)
    timing: Optional[dict[str, float]] = field(default=None, repr=False, compare=False)


class FacePipeline:
    """Holds long-lived models. Thread-safe for read-only `process` calls in
    CPython because the underlying torch/onnxruntime calls release the GIL
    and the dataclasses are not shared mutable state.
    """

    def __init__(
        self,
        detector: Detector,
        embedder: Embedder,
        anti_spoof: Optional[AntiSpoof] = None,
        align_size: int = 112,
    ):
        self._detector = detector
        self._embedder = embedder
        self._anti_spoof = anti_spoof
        self._align_size = align_size

    @property
    def embedding_dim(self) -> int:
        return self._embedder.embedding_dim

    def process(
        self,
        image_bgr: np.ndarray,
        max_faces: int = 0,
        skip_anti_spoof: bool = False,
        collect_timing: bool = False,
    ) -> FrameResult:
        """Run the full pipeline.

        Args:
            image_bgr: full-frame BGR uint8.
            max_faces: 0 = all detections; else top-N by score.
            skip_anti_spoof: bypass the FAS gate even if a predictor is wired.
            collect_timing: attach per-stage elapsed milliseconds to FrameResult.

        For each detected face we (1) align to 112x112, (2) optionally run
        anti-spoof, and (3) embed only when the face is real (or FAS off).
        """
        timing = {
            "detect": 0.0,
            "align": 0.0,
            "liveness": 0.0,
            "embed": 0.0,
        } if collect_timing else None
        result = FrameResult(timing=timing)

        def _started() -> float | None:
            if timing is None:
                return None
            try:
                return time.perf_counter()
            except Exception:
                return None

        def _add_elapsed(stage: str, started: float | None) -> None:
            if timing is None or started is None:
                return
            try:
                timing[stage] = timing.get(stage, 0.0) + (time.perf_counter() - started) * 1000.0
            except Exception:
                # Timing is observability-only; never affect inference.
                pass

        started = _started()
        dets = self._detector.detect(image_bgr, max_num=max_faces)
        _add_elapsed("detect", started)
        if not dets:
            return result

        aligned_for_embed: list[np.ndarray] = []
        records_for_embed: list[FaceRecord] = []

        for det in dets:
            started = _started()
            aligned = align_112(image_bgr, det.kps, output_size=self._align_size)
            _add_elapsed("align", started)
            rec = FaceRecord(detection=det, aligned_112=aligned)

            if self._anti_spoof is not None and not skip_anti_spoof:
                started = _started()
                spoof = self._anti_spoof.predict(image_bgr, det.bbox)
                _add_elapsed("liveness", started)
                rec.spoof = spoof
                if not spoof.is_real:
                    rec.skipped_reason = f"anti_spoof_rejected(score={spoof.real_score:.3f})"
                    result.faces.append(rec)
                    continue

            aligned_for_embed.append(aligned)
            records_for_embed.append(rec)
            result.faces.append(rec)

        if aligned_for_embed:
            started = _started()
            embs = self._embedder.embed(aligned_for_embed)
            _add_elapsed("embed", started)
            for rec, emb in zip(records_for_embed, embs):
                rec.embedding = emb

        return result


def build_default_pipeline(settings) -> FacePipeline:
    """Construct a FacePipeline from a `app.settings.Settings` instance.

    Centralised here so CLI scripts and FastAPI both share one builder.
    """
    detector = create_detector(
        settings.detector.get("backend", "scrfd"),
        settings.detector,
        settings,
    )
    embedder = create_embedder(
        settings.embedder.get("backend", "edgeface"),
        settings.embedder,
        settings,
    )
    anti_spoof = None
    if bool(settings.anti_spoof.get("enabled", True)):
        anti_spoof = create_anti_spoof(
            settings.anti_spoof.get("backend", "minifas"),
            settings.anti_spoof,
            settings,
        )
    return FacePipeline(detector=detector, embedder=embedder, anti_spoof=anti_spoof)
