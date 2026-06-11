"""Loads config.yaml once and exposes typed accessors. Pure I/O, no model loading."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

APP_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = APP_DIR / "config.yaml"


def _resolve(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else (APP_DIR / p).resolve()


@dataclass
class Settings:
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG) -> "Settings":
        with open(path, "r", encoding="utf-8") as f:
            return cls(raw=yaml.safe_load(f))

    # path helpers
    @property
    def edgeface_repo(self) -> Path: return _resolve(self.raw["paths"]["edgeface_repo"])
    @property
    def silent_fas_repo(self) -> Path: return _resolve(self.raw["paths"]["silent_fas_repo"])
    @property
    def data_dir(self) -> Path:
        d = _resolve(self.raw["paths"]["data_dir"])
        d.mkdir(parents=True, exist_ok=True)
        return d
    @property
    def insightface_root(self) -> Path:
        d = _resolve(self.raw["paths"]["insightface_root"])
        d.mkdir(parents=True, exist_ok=True)
        return d
    @property
    def antispoof_model_dir(self) -> Path: return _resolve(self.raw["anti_spoof"]["model_dir"])
    @property
    def embedder_checkpoint(self) -> Path: return _resolve(self.raw["embedder"]["checkpoint"])
    @property
    def frontend_dist(self) -> Path: return _resolve(self.raw["frontend"]["dist_dir"])

    # section accessors
    @property
    def detector(self) -> dict: return self.raw["detector"]
    @property
    def aligner(self) -> dict: return self.raw["aligner"]
    @property
    def anti_spoof(self) -> dict: return self.raw["anti_spoof"]
    @property
    def embedder(self) -> dict: return self.raw["embedder"]
    @property
    def api(self) -> dict: return self.raw["api"]
