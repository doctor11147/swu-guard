"""EdgeFace embedding extractor (uses local checkpoints).

Notes
-----
- EdgeFace's own `face_alignment/align.py` hard-codes `device='cuda:0'` and
  uses an internal MTCNN. We bypass it entirely; alignment is handled by
  `core.aligner` (5-point similarity transform on SCRFD landmarks), which
  is the canonical ArcFace pipeline.
- Input contract: 112x112 BGR uint8 (output of `core.aligner.align_112`).
  We convert BGR->RGB and apply the standard mean=0.5/std=0.5 normalisation
  documented in EdgeFace's README.
- Output: L2-normalised float32 vector of size 512. L2-normalising here means
  cosine similarity reduces to inner product downstream (FAISS IndexFlatIP).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import torch
import torch.nn.functional as F


def _ensure_edgeface_on_path(repo_root: Path) -> None:
    repo_root = repo_root.resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def _resolve_device(spec: str) -> torch.device:
    if spec == "cpu":
        return torch.device("cpu")
    if spec == "cuda":
        return torch.device("cuda")
    if spec == "mps":
        return torch.device("mps")
    if spec == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    raise ValueError(f"unknown device spec: {spec}")


# ImageNet-style mean=0.5/std=0.5 normalisation in [0,1] domain.
_MEAN = torch.tensor([0.5, 0.5, 0.5], dtype=torch.float32).view(1, 3, 1, 1)
_STD = torch.tensor([0.5, 0.5, 0.5], dtype=torch.float32).view(1, 3, 1, 1)


class EdgeFaceEmbedder:
    def __init__(
        self,
        model_name: str,
        checkpoint: str | Path,
        repo_root: str | Path,
        device: str = "auto",
    ):
        _ensure_edgeface_on_path(Path(repo_root))
        from backbones import get_model  # noqa: WPS433

        self._device = _resolve_device(device)
        self._model = get_model(model_name)
        state = torch.load(str(checkpoint), map_location="cpu")
        self._model.load_state_dict(state)
        self._model.to(self._device).eval()
        self._mean = _MEAN.to(self._device)
        self._std = _STD.to(self._device)
        self.embedding_dim = 512  # EdgeFace TimmFRWrapperV2 output

    def _preprocess_batch(self, faces_112_bgr: Sequence[np.ndarray]) -> torch.Tensor:
        # Stack to (N, 112, 112, 3) uint8 RGB.
        rgb = np.stack([cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in faces_112_bgr], axis=0)
        # (N, H, W, C) -> (N, C, H, W) float in [0,1]
        t = torch.from_numpy(rgb).to(self._device, non_blocking=True)
        t = t.permute(0, 3, 1, 2).float().div_(255.0)
        return (t - self._mean) / self._std

    @torch.inference_mode()
    def embed(self, faces_112_bgr: Sequence[np.ndarray]) -> np.ndarray:
        """Return (N, 512) L2-normalised embeddings as float32 numpy."""
        if len(faces_112_bgr) == 0:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        for i, f in enumerate(faces_112_bgr):
            if f.shape != (112, 112, 3) or f.dtype != np.uint8:
                raise ValueError(f"face {i}: expected (112,112,3) uint8, got {f.shape} {f.dtype}")
        x = self._preprocess_batch(faces_112_bgr)
        feats = self._model(x)
        feats = F.normalize(feats, p=2, dim=1)
        return feats.detach().to("cpu").numpy().astype(np.float32, copy=False)

    def embed_one(self, face_112_bgr: np.ndarray) -> np.ndarray:
        """Return a single (512,) L2-normalised embedding."""
        return self.embed([face_112_bgr])[0]
