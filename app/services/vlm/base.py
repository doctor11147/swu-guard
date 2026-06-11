"""Abstract VLM provider interface.

Every VLM provider (DeepSeek, Qwen, GLM, mock) MUST implement ``assess_scene``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from app.schemas.adaptive import VLMSceneAssessment


class VLMProvider(ABC):
    """Base interface for vision-language model scene assessment.

    Providers receive a single BGR frame sampled from the gate camera
    and MUST return a structured ``VLMSceneAssessment``.

    Contract:
      - NEVER identify persons, output biometric conclusions, or suggest thresholds.
      - Return a JSON-parsed VLMSceneAssessment or raise VLMError on failure.
    """

    @abstractmethod
    async def assess_scene(
        self, frame_bgr: np.ndarray, *, temp_dir: str | None = None,
    ) -> VLMSceneAssessment:
        """Assess gate scene from one sampled BGR frame."""
        ...


class VLMError(Exception):
    """Non-retryable VLM call failure.  The orchestrator should fall back."""
