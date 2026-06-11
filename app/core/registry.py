"""Algorithm backend registry for the face recognition pipeline.

Backends register lightweight factory functions here. The registry is independent
from FastAPI and database code so pipeline construction can stay plug-and-play.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Protocol, TypeVar, runtime_checkable

import numpy as np

from .anti_spoof import SpoofResult
from .detector import Detection


@runtime_checkable
class Detector(Protocol):
    """Face detector contract: BGR frame -> scored boxes and five landmarks."""

    def detect(self, image_bgr: np.ndarray, max_num: int = 0) -> list[Detection]:
        """Return detections sorted by confidence descending."""


@runtime_checkable
class Embedder(Protocol):
    """Face embedder contract: aligned 112x112 BGR crops -> L2 vectors."""

    embedding_dim: int

    def embed(self, faces: Sequence[np.ndarray]) -> np.ndarray:
        """Return an (N, embedding_dim) float32 L2-normalised matrix."""


@runtime_checkable
class AntiSpoof(Protocol):
    """Anti-spoofing contract: original BGR frame + face bbox -> liveness score."""

    def predict(self, image_bgr: np.ndarray, bbox) -> SpoofResult:
        """Return liveness decision and real-face score."""


@runtime_checkable
class QualityAssessor(Protocol):
    """Quality assessor contract for aligned 112x112 BGR face crops."""

    def score(self, face_bgr: np.ndarray) -> float:
        """Return a scalar quality score; higher means better."""


T = TypeVar("T")
Factory = Callable[[dict[str, Any], Any], T]

_DETECTORS: dict[str, Factory[Detector]] = {}
_EMBEDDERS: dict[str, Factory[Embedder]] = {}
_ANTI_SPOOFERS: dict[str, Factory[AntiSpoof]] = {}
_QUALITY_ASSESSORS: dict[str, Factory[QualityAssessor]] = {}


def _normalise_name(name: str) -> str:
    value = name.strip().lower()
    if not value:
        raise ValueError("backend name must not be empty")
    return value


def _register(registry: dict[str, Factory[T]], name: str, factory: Factory[T]) -> Factory[T]:
    registry[_normalise_name(name)] = factory
    return factory


def _create(registry: dict[str, Factory[T]], kind: str, name: str, cfg: dict[str, Any], settings: Any) -> T:
    backend = _normalise_name(name)
    try:
        factory = registry[backend]
    except KeyError as exc:
        available = ", ".join(sorted(registry)) or "<none>"
        raise ValueError(f"unknown {kind} backend '{name}', available: {available}") from exc
    return factory(cfg, settings)


def register_detector(name: str) -> Callable[[Factory[Detector]], Factory[Detector]]:
    def decorator(factory: Factory[Detector]) -> Factory[Detector]:
        return _register(_DETECTORS, name, factory)
    return decorator


def register_embedder(name: str) -> Callable[[Factory[Embedder]], Factory[Embedder]]:
    def decorator(factory: Factory[Embedder]) -> Factory[Embedder]:
        return _register(_EMBEDDERS, name, factory)
    return decorator


def register_anti_spoof(name: str) -> Callable[[Factory[AntiSpoof]], Factory[AntiSpoof]]:
    def decorator(factory: Factory[AntiSpoof]) -> Factory[AntiSpoof]:
        return _register(_ANTI_SPOOFERS, name, factory)
    return decorator


def register_quality(name: str) -> Callable[[Factory[QualityAssessor]], Factory[QualityAssessor]]:
    def decorator(factory: Factory[QualityAssessor]) -> Factory[QualityAssessor]:
        return _register(_QUALITY_ASSESSORS, name, factory)
    return decorator


def create_detector(name: str, cfg: dict[str, Any], settings: Any) -> Detector:
    return _create(_DETECTORS, "detector", name, cfg, settings)


def create_embedder(name: str, cfg: dict[str, Any], settings: Any) -> Embedder:
    return _create(_EMBEDDERS, "embedder", name, cfg, settings)


def create_anti_spoof(name: str, cfg: dict[str, Any], settings: Any) -> AntiSpoof:
    return _create(_ANTI_SPOOFERS, "anti_spoof", name, cfg, settings)


def create_quality(name: str, cfg: dict[str, Any], settings: Any) -> QualityAssessor:
    return _create(_QUALITY_ASSESSORS, "quality", name, cfg, settings)


@register_detector("scrfd")
def _scrfd_factory(cfg: dict[str, Any], settings: Any) -> Detector:
    from .detector import SCRFDDetector

    return SCRFDDetector(
        bundle=cfg["bundle"],
        root=settings.insightface_root,
        det_size=tuple(cfg["det_size"]),
        det_thresh=float(cfg["det_thresh"]),
        ctx_id=int(cfg["ctx_id"]),
    )


@register_embedder("edgeface")
def _edgeface_factory(cfg: dict[str, Any], settings: Any) -> Embedder:
    from .embedder import EdgeFaceEmbedder

    return EdgeFaceEmbedder(
        model_name=cfg["model_name"],
        checkpoint=settings.embedder_checkpoint,
        repo_root=settings.edgeface_repo,
        device=str(cfg["device"]),
    )


class _DummyEmbedder:
    """Deterministic test backend for registry wiring checks."""

    embedding_dim = 512

    def embed(self, faces: Sequence[np.ndarray]) -> np.ndarray:
        vectors = np.zeros((len(faces), self.embedding_dim), dtype=np.float32)
        if len(faces):
            vectors[:, 0] = 1.0
        return vectors


@register_embedder("dummy")
def _dummy_embedder_factory(cfg: dict[str, Any], settings: Any) -> Embedder:
    return _DummyEmbedder()


@register_anti_spoof("minifas")
def _minifas_factory(cfg: dict[str, Any], settings: Any) -> AntiSpoof:
    from .anti_spoof import SilentFASPredictor

    return SilentFASPredictor(
        model_dir=settings.antispoof_model_dir,
        repo_root=settings.silent_fas_repo,
        real_threshold=float(cfg["real_threshold"]),
    )


@register_quality("laplacian")
def _laplacian_factory(cfg: dict[str, Any], settings: Any) -> QualityAssessor:
    from .quality import get_quality_assessor

    return get_quality_assessor(device=str(cfg.get("device", "cpu")))
