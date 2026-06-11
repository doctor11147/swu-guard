"""MiniVision Silent-Face Anti-Spoofing wrapper.

Design notes
------------
- Upstream `AntiSpoofPredict` inherits `Detection` whose `__init__` calls
  `cv2.dnn.readNetFromCaffe("./resources/...")` with a *relative* path. That
  only works if cwd == Silent-Face-Anti-Spoofing root. We don't want that
  global-state coupling; we already have a SCRFD bbox from `core.detector`.
  So we re-implement the predict path, reusing only the upstream MiniFASNet
  module factory (`MODEL_MAPPING`) and the patch-cropper (`CropImage`).
- Each MiniFAS checkpoint encodes (h, w, model_type, scale) in its filename.
  We ensemble all checkpoints in `model_dir` by mean-of-softmax, exactly as
  the official `test.py` does (sums then divides by 2 — generalised to N here).
- Class index 1 is "real face" (the other two are print/replay attacks).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F


def _ensure_silent_fas_on_path(repo_root: Path) -> None:
    repo_root = repo_root.resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


@dataclass
class SpoofResult:
    is_real: bool
    real_score: float          # softmax-mean for class "real" in [0, 1]
    label: int                 # argmax over 3 classes (1 == real)
    per_model_scores: dict[str, np.ndarray]  # filename -> (3,) softmax


class SilentFASPredictor:
    """Loads every *.pth in `model_dir` once and holds them on `device`."""

    def __init__(
        self,
        model_dir: str | Path,
        repo_root: str | Path,
        device: str | torch.device | None = None,
        real_threshold: float = 0.85,
    ):
        _ensure_silent_fas_on_path(Path(repo_root))
        # Upstream modules import as `from src.model_lib... ` etc. They live
        # inside the repo we just put on sys.path.
        from src.generate_patches import CropImage  # noqa: WPS433
        from src.model_lib.MiniFASNet import (  # noqa: WPS433
            MiniFASNetV1, MiniFASNetV2, MiniFASNetV1SE, MiniFASNetV2SE,
        )
        from src.utility import get_kernel, parse_model_name  # noqa: WPS433

        self._cropper = CropImage()
        self._parse = parse_model_name
        self._real_threshold = float(real_threshold)
        self._model_dir = Path(model_dir)
        self._device = torch.device(device) if device else (
            torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        )

        mapping = {
            "MiniFASNetV1": MiniFASNetV1, "MiniFASNetV2": MiniFASNetV2,
            "MiniFASNetV1SE": MiniFASNetV1SE, "MiniFASNetV2SE": MiniFASNetV2SE,
        }

        self._models: list[dict] = []
        for fname in sorted(os.listdir(self._model_dir)):
            if not fname.endswith(".pth"):
                continue
            h, w, mtype, scale = self._parse(fname)
            kernel = get_kernel(h, w)
            net = mapping[mtype](conv6_kernel=kernel).to(self._device)
            state = torch.load(self._model_dir / fname, map_location=self._device)
            # Strip DataParallel "module." prefix if present.
            if next(iter(state)).startswith("module."):
                state = {k[len("module."):]: v for k, v in state.items()}
            net.load_state_dict(state)
            net.eval()
            self._models.append(dict(
                name=fname, net=net, h=h, w=w, scale=scale,
            ))
        if not self._models:
            raise FileNotFoundError(f"No .pth weights found in {self._model_dir}")

    @staticmethod
    def _xyxy_to_xywh(xyxy: np.ndarray) -> list[int]:
        x1, y1, x2, y2 = xyxy.astype(int).tolist()
        return [x1, y1, max(1, x2 - x1), max(1, y2 - y1)]

    @torch.inference_mode()
    def predict(self, image_bgr: np.ndarray, bbox_xyxy: np.ndarray) -> SpoofResult:
        """Score one face given the original image and its xyxy bbox."""
        bbox_xywh = self._xyxy_to_xywh(bbox_xyxy)
        prob_sum = np.zeros(3, dtype=np.float32)
        per_model: dict[str, np.ndarray] = {}

        for cfg in self._models:
            patch = self._cropper.crop(
                org_img=image_bgr,
                bbox=bbox_xywh,
                scale=cfg["scale"],
                out_w=cfg["w"], out_h=cfg["h"],
                crop=cfg["scale"] is not None,
            )
            # Match upstream preprocessing EXACTLY. Silent-FAS's `to_tensor`
            # in src/data_io/functional.py kept `img.float().div(255)`
            # COMMENTED OUT ("modify by zkx" / "backward compatibility").
            # The shipped MiniFASNet weights therefore expect inputs in the
            # [0, 255] range, NOT [0, 1]. Dividing here drops real_score to
            # ~0.01 because the input distribution is 255x off from training.
            x = torch.from_numpy(patch).permute(2, 0, 1).float()
            x = x.unsqueeze(0).to(self._device)
            logits = cfg["net"](x)
            probs = F.softmax(logits, dim=1).squeeze(0).cpu().numpy()
            prob_sum += probs
            per_model[cfg["name"]] = probs

        prob_mean = prob_sum / len(self._models)
        label = int(np.argmax(prob_mean))
        real_score = float(prob_mean[1])
        return SpoofResult(
            is_real=(label == 1) and (real_score >= self._real_threshold),
            real_score=real_score,
            label=label,
            per_model_scores=per_model,
        )
