"""End-to-end smoke test (no FastAPI, no DB).

Loads the pipeline once, runs it on a single image, prints the result.

Usage:
    cd /path/to/face
    conda activate face
    python -m app.scripts.smoke_test path/to/face.jpg
"""
from __future__ import annotations

import argparse
import sys

import cv2

from app.core.pipeline import build_default_pipeline
from app.settings import Settings


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("image", help="path to a face image")
    p.add_argument("--no-spoof", action="store_true", help="skip anti-spoof gate")
    args = p.parse_args()

    img = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if img is None:
        print(f"could not read {args.image}", file=sys.stderr)
        return 1

    settings = Settings.load()
    pipeline = build_default_pipeline(settings)
    print(f"pipeline ready. embedding_dim={pipeline.embedding_dim}")

    frame = pipeline.process(img, skip_anti_spoof=args.no_spoof)
    if not frame.faces:
        print("no faces detected")
        return 0

    for i, f in enumerate(frame.faces):
        det = f.detection
        print(f"--- face {i} ---")
        print(f"  bbox={det.bbox.tolist()} score={det.score:.3f}")
        if f.spoof is not None:
            print(f"  spoof: real={f.spoof.is_real} real_score={f.spoof.real_score:.3f} "
                  f"label={f.spoof.label}")
        if f.embedding is not None:
            v = f.embedding
            print(f"  emb dim={v.shape[0]} norm={float((v ** 2).sum()) ** 0.5:.4f} "
                  f"(should be ~1.0)")
        else:
            print(f"  no embedding (skipped: {f.skipped_reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
