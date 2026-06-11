"""LFW 1:1 verification evaluation of the embedder (end-to-end with detection+alignment).

Reads the standard 6000-pair LFW protocol from a local Kaggle-style dump
(the `jessicali9530/lfw-dataset` layout):

    <lfw-dir>/
      pairs.csv
      lfw-deepfunneled/
        lfw-deepfunneled/
          <Name>/<Name>_NNNN.jpg

`pairs.csv` is the canonical 10-fold-x-600 split. Per row:
    same-person  : "<name>,<num1>,<num2>,"        (4 fields, last empty)
    diff-person  : "<name1>,<num1>,<name2>,<num2>" (4 fields)

We keep the row order so 10-fold CV uses the canonical folds, not random.

Usage:
    conda activate face
    python -m app.scripts.eval_lfw \\
        --lfw-dir /path/to/lfw \\
        [--max-pairs 600]

Anti-spoof is always disabled here: LFW is single-frame benchmark imagery and
the FAS gate would only inject noise.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from app.core.pipeline import build_default_pipeline
from app.settings import Settings


@dataclass
class Pair:
    img_a: Path
    img_b: Path
    same: int  # 1 if same identity, else 0


def _img_path(images_root: Path, name: str, num: int) -> Path:
    return images_root / name / f"{name}_{int(num):04d}.jpg"


def load_pairs(lfw_dir: Path) -> list[Pair]:
    """Parse pairs.csv into (path_a, path_b, same)."""
    pairs_csv = lfw_dir / "pairs.csv"
    if not pairs_csv.exists():
        raise FileNotFoundError(f"missing {pairs_csv}")
    images_root = lfw_dir / "lfw-deepfunneled" / "lfw-deepfunneled"
    if not images_root.exists():
        # Some unzip tools collapse the double directory.
        alt = lfw_dir / "lfw-deepfunneled"
        if (alt / next(iter(alt.iterdir())).name).is_dir():
            images_root = alt

    pairs: list[Pair] = []
    with open(pairs_csv, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            # Normalise to exactly 4 cells (csv may yield 3 or 5 in edge cases).
            cells = [c.strip() for c in row]
            while len(cells) < 4:
                cells.append("")
            cells = cells[:4]
            name1, num1, c3, c4 = cells
            if not name1:
                continue
            if c4 == "":
                # same-person: name, num1, num2, ""
                p = Pair(
                    img_a=_img_path(images_root, name1, int(num1)),
                    img_b=_img_path(images_root, name1, int(c3)),
                    same=1,
                )
            else:
                # diff-person: name1, num1, name2, num2
                p = Pair(
                    img_a=_img_path(images_root, name1, int(num1)),
                    img_b=_img_path(images_root, c3, int(c4)),
                    same=0,
                )
            pairs.append(p)
    return pairs


def _embed(pipeline, image_bgr: np.ndarray) -> np.ndarray | None:
    frame = pipeline.process(image_bgr, max_faces=1, skip_anti_spoof=True)
    if not frame.faces or frame.faces[0].embedding is None:
        return None
    return frame.faces[0].embedding


def embed_unique(pipeline, paths: Sequence[Path]) -> dict[Path, np.ndarray]:
    """Cache one embedding per unique image path (LFW images appear in many pairs)."""
    cache: dict[Path, np.ndarray] = {}
    unique = sorted(set(paths))
    n = len(unique)
    print(f"embedding {n} unique images...")
    for i, p in enumerate(unique, 1):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue
        emb = _embed(pipeline, img)
        if emb is not None:
            cache[p] = emb
        if i % 200 == 0:
            print(f"  {i}/{n} (cached={len(cache)})")
    print(f"done: {len(cache)}/{n} embeddings cached")
    return cache


def kfold_canonical(scores: np.ndarray, labels: np.ndarray, k: int = 10) -> tuple[float, float, list[float]]:
    """LFW canonical k-fold: pairs are pre-ordered into k contiguous blocks,
    each block has equal positives and negatives. We pick the best threshold
    on the (k-1) training folds and evaluate on the held-out fold.
    """
    n = len(scores)
    if n % k != 0:
        # Fall back to the closest split; warn.
        print(f"warning: {n} pairs not divisible by k={k}; using array_split")
    folds = np.array_split(np.arange(n), k)
    cand = np.linspace(float(scores.min()), float(scores.max()), 400)
    accs: list[float] = []
    thrs: list[float] = []
    for i in range(k):
        test = folds[i]
        train = np.concatenate([folds[j] for j in range(k) if j != i])
        s_tr, y_tr = scores[train], labels[train]
        s_te, y_te = scores[test], labels[test]
        # Best train accuracy across candidate thresholds (cosine similarity).
        train_accs = ((s_tr[None, :] >= cand[:, None]) == y_tr[None, :]).mean(axis=1)
        best = float(cand[int(np.argmax(train_accs))])
        accs.append(float(((s_te >= best) == y_te).mean()))
        thrs.append(best)
    return float(np.mean(accs)), float(np.mean(thrs)), accs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lfw-dir", required=True, type=Path,
                    help="Kaggle LFW root containing pairs.csv and lfw-deepfunneled/")
    ap.add_argument("--max-pairs", type=int, default=0,
                    help="0 = all 6000 pairs; otherwise truncate (preserves fold balance only if multiple of 600)")
    ap.add_argument("--folds", type=int, default=10)
    args = ap.parse_args()

    pairs = load_pairs(args.lfw_dir)
    if args.max_pairs > 0:
        pairs = pairs[: args.max_pairs]
    print(f"loaded {len(pairs)} pairs from {args.lfw_dir}")

    settings = Settings.load()
    pipeline = build_default_pipeline(settings)

    all_paths = [p for pair in pairs for p in (pair.img_a, pair.img_b)]
    cache = embed_unique(pipeline, all_paths)

    scores: list[float] = []
    labels: list[int] = []
    skipped = 0
    for pair in pairs:
        ea = cache.get(pair.img_a)
        eb = cache.get(pair.img_b)
        if ea is None or eb is None:
            skipped += 1
            continue
        scores.append(float(np.dot(ea, eb)))
        labels.append(pair.same)

    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int64)
    pos = s[y == 1]
    neg = s[y == 0]
    print(f"\npairs scored: {len(s)}  pos={len(pos)} neg={len(neg)} skipped={skipped}")
    if len(pos) == 0 or len(neg) == 0:
        print("not enough pairs to evaluate")
        return 1

    print(f"pos cos: mean={pos.mean():.4f} std={pos.std():.4f} min={pos.min():.3f} max={pos.max():.3f}")
    print(f"neg cos: mean={neg.mean():.4f} std={neg.std():.4f} min={neg.min():.3f} max={neg.max():.3f}")

    # Global best (single threshold over the whole set; informational, not the protocol metric).
    cand = np.linspace(s.min(), s.max(), 400)
    global_acc = ((s[None, :] >= cand[:, None]) == y[None, :]).mean(axis=1)
    g_idx = int(np.argmax(global_acc))
    print(f"global best thr={cand[g_idx]:.3f}  acc={global_acc[g_idx]:.4f}")

    acc, thr, fold_accs = kfold_canonical(s, y, k=args.folds)
    print(f"\n{args.folds}-fold mean acc = {acc:.4f}  mean best threshold = {thr:.3f}")
    print(f"per-fold acc: {[f'{a:.4f}' for a in fold_accs]}")

    print("\n--> recommended app/config.yaml: embedder.match_threshold ≈ "
          f"{thr:.2f}  (current default 0.40)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
