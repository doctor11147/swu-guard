"""Rebuild app/data/faces.faiss from MySQL metadata and original face images.

`face_embeddings` stores metadata only; vectors are regenerated from each row's
`image_path` using the configured pipeline, then written to a fresh FAISS
IndexIDMap2 with the original embedding row id as the FAISS id.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import faiss
import numpy as np
from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.pipeline import build_default_pipeline
from app.settings import Settings
from app.store.faiss_index import FaissStore
from app.store.models import FaceEmbedding
from app.store.session import db_session


@dataclass(slots=True)
class RebuildRow:
    embedding_id: int
    person_id: int
    image_path: str | None


@dataclass(slots=True)
class RebuildFailure:
    embedding_id: int
    image_path: str | None
    reason: str


async def _load_rows() -> list[RebuildRow]:
    async with db_session() as session:
        rows = (await session.execute(
            select(FaceEmbedding.id, FaceEmbedding.person_id, FaceEmbedding.image_path)
            .order_by(FaceEmbedding.id),
        )).all()
    return [
        RebuildRow(
            embedding_id=int(row.id),
            person_id=int(row.person_id),
            image_path=str(row.image_path) if row.image_path is not None else None,
        )
        for row in rows
    ]


def _decode_image(path_text: str | None) -> np.ndarray | None:
    if not path_text:
        return None
    path = Path(path_text).expanduser()
    if not path.exists():
        return None
    raw = np.fromfile(str(path), dtype=np.uint8)
    if raw.size == 0:
        return None
    return cv2.imdecode(raw, cv2.IMREAD_COLOR)


def _write_rebuilt_index(
    *,
    vectors: list[np.ndarray],
    ids: list[int],
    target_path: Path,
    dim: int,
) -> None:
    rebuild_path = target_path.with_suffix(target_path.suffix + ".rebuild")
    if rebuild_path.exists():
        rebuild_path.unlink()
    store = FaissStore(dim=dim, index_path=rebuild_path)
    if vectors:
        store.add(np.stack(vectors, axis=0), ids)
    store.save()
    os.replace(rebuild_path, target_path)


def _verify_index(path: Path, expected_ids: list[int], dim: int) -> tuple[int, list[int], list[int]]:
    index = faiss.read_index(str(path))
    if int(index.d) != int(dim):
        raise RuntimeError(f"rebuilt index dim {index.d} != expected {dim}")
    if not hasattr(index, "id_map"):
        raise RuntimeError("rebuilt index has no id_map")
    actual_ids = {int(i) for i in faiss.vector_to_array(index.id_map)}
    expected = {int(i) for i in expected_ids}
    return int(index.ntotal), sorted(expected - actual_ids), sorted(actual_ids - expected)


async def _amain() -> int:
    settings = Settings.load()
    parser = argparse.ArgumentParser(description="Rebuild app/data/faces.faiss from MySQL face_embeddings.image_path")
    parser.add_argument("--faiss", type=Path, default=settings.data_dir / "faces.faiss", help="Target FAISS index path")
    parser.add_argument("--dry-run", action="store_true", help="Read DB/images and regenerate vectors without replacing the index")
    parser.add_argument("--allow-partial", action="store_true", help="Replace the index even when some DB rows cannot be rebuilt")
    parser.add_argument("--skip-anti-spoof", action="store_true", help="Bypass liveness during rebuild embedding generation")
    args = parser.parse_args()

    rows = await _load_rows()
    print(f"DB face_embeddings : {len(rows)}")
    print(f"Target FAISS       : {args.faiss}")
    print(f"Dry run            : {args.dry_run}")

    pipeline = build_default_pipeline(settings)
    vectors: list[np.ndarray] = []
    ids: list[int] = []
    failures: list[RebuildFailure] = []

    for row in rows:
        img = _decode_image(row.image_path)
        if img is None:
            failures.append(RebuildFailure(row.embedding_id, row.image_path, "image_missing_or_decode_failed"))
            continue

        try:
            frame = pipeline.process(
                img,
                max_faces=1,
                skip_anti_spoof=bool(args.skip_anti_spoof),
            )
        except Exception as exc:
            failures.append(RebuildFailure(row.embedding_id, row.image_path, f"pipeline_failed:{type(exc).__name__}:{exc}"))
            continue

        if not frame.faces:
            failures.append(RebuildFailure(row.embedding_id, row.image_path, "no_face"))
            continue
        face = frame.faces[0]
        if face.embedding is None:
            reason = face.skipped_reason or "embedding_missing"
            failures.append(RebuildFailure(row.embedding_id, row.image_path, reason))
            continue

        vectors.append(face.embedding.astype(np.float32, copy=False))
        ids.append(row.embedding_id)

    print(f"Vectors rebuilt    : {len(vectors)}")
    print(f"Failures           : {len(failures)}")
    for failure in failures[:20]:
        print(f"  - id={failure.embedding_id} reason={failure.reason} image={failure.image_path}")
    if len(failures) > 20:
        print(f"  ... {len(failures) - 20} more failures")

    if failures and not args.allow_partial:
        print("Abort: failures found. Re-run with --allow-partial only if a partial index is intentional.")
        return 2

    if args.dry_run:
        print("Dry run complete; FAISS file was not changed.")
        return 0

    _write_rebuilt_index(
        vectors=vectors,
        ids=ids,
        target_path=args.faiss,
        dim=pipeline.embedding_dim,
    )
    ntotal, missing_ids, extra_ids = _verify_index(args.faiss, ids, pipeline.embedding_dim)
    print(f"Rebuilt ntotal     : {ntotal}")
    print(f"Missing rebuilt ids: {len(missing_ids)} {missing_ids[:20]}")
    print(f"Extra rebuilt ids  : {len(extra_ids)} {extra_ids[:20]}")
    if missing_ids or extra_ids:
        return 3
    print("FAISS rebuild complete.")
    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
