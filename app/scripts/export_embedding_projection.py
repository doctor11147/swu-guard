"""Export a 2D projection of registered face embeddings for the frontend.

The output contains only non-sensitive labels and projected coordinates. It
does not include source image paths, external ids, or raw 512-D vectors.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Literal, NamedTuple

import faiss
import numpy as np
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.settings import Settings
from app.store.session import db_session

Method = Literal["auto", "umap", "tsne", "pca"]


class EmbeddingMeta(NamedTuple):
    embedding_id: int
    person_id: int
    name: str
    role: str


def _read_faiss_vectors(faiss_path: Path) -> tuple[dict[int, np.ndarray], int]:
    if not faiss_path.exists():
        raise FileNotFoundError(f"FAISS index not found: {faiss_path}")

    index = faiss.read_index(str(faiss_path))
    if not hasattr(index, "id_map"):
        raise RuntimeError("FAISS index has no id_map; cannot align ids with MySQL")

    ids = [int(i) for i in faiss.vector_to_array(index.id_map)]
    vectors: dict[int, np.ndarray] = {}
    for embedding_id in ids:
        vec = np.zeros((index.d,), dtype=np.float32)
        index.reconstruct(embedding_id, vec)
        vectors[embedding_id] = vec
    return vectors, int(index.ntotal)


async def _read_mysql_metadata() -> dict[int, EmbeddingMeta]:
    sql = text("""
        select
            fe.id as embedding_id,
            p.id as person_id,
            p.name as name,
            p.role as role
        from face_embeddings fe
        join persons p on p.id = fe.person_id
        where p.deleted_at is null
        order by fe.id
    """)
    async with db_session() as session:
        rows = (await session.execute(sql)).mappings().all()

    return {
        int(row["embedding_id"]): EmbeddingMeta(
            embedding_id=int(row["embedding_id"]),
            person_id=int(row["person_id"]),
            name=str(row["name"] or "未命名"),
            role=str(row["role"] or "unknown"),
        )
        for row in rows
    }


def _project_pca(vectors: np.ndarray) -> tuple[np.ndarray, str]:
    from sklearn.decomposition import PCA

    if len(vectors) == 1:
        return np.zeros((1, 2), dtype=np.float32), "pca"
    pca = PCA(n_components=min(2, len(vectors)), random_state=42)
    projected = pca.fit_transform(vectors)
    if projected.shape[1] == 1:
        projected = np.column_stack([projected[:, 0], np.zeros(len(projected))])
    return projected.astype(np.float32), "pca"


def _project_tsne(vectors: np.ndarray) -> tuple[np.ndarray, str]:
    from sklearn.manifold import TSNE

    if len(vectors) < 4:
        return _project_pca(vectors)
    perplexity = min(30, max(2, (len(vectors) - 1) // 3))
    projected = TSNE(
        n_components=2,
        perplexity=perplexity,
        init="random",
        learning_rate=200.0,
        metric="cosine",
        random_state=42,
    ).fit_transform(vectors)
    return projected.astype(np.float32), "tsne"


def _project_umap(vectors: np.ndarray) -> tuple[np.ndarray, str]:
    if len(vectors) < 4:
        return _project_pca(vectors)
    try:
        import umap  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError("umap-learn is not installed") from exc

    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=min(15, max(2, len(vectors) - 1)),
        min_dist=0.12,
        metric="cosine",
        random_state=42,
    )
    return reducer.fit_transform(vectors).astype(np.float32), "umap"


def _project(vectors: np.ndarray, method: Method) -> tuple[np.ndarray, str]:
    if method == "pca":
        return _project_pca(vectors)
    if method == "tsne":
        return _project_tsne(vectors)
    if method == "umap":
        return _project_umap(vectors)

    try:
        return _project_umap(vectors)
    except Exception:
        return _project_tsne(vectors)


def _normalize(points: np.ndarray) -> np.ndarray:
    centered = points - points.mean(axis=0, keepdims=True)
    scale = float(np.max(np.linalg.norm(centered, axis=1))) if len(centered) else 0.0
    if scale <= 1e-9:
        return centered
    return centered / scale


def _write_json_atomic(path: Path, payload: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


async def _amain() -> int:
    settings = Settings.load()
    parser = argparse.ArgumentParser(description="Export frontend/public/eval/embedding_2d.json")
    parser.add_argument("--faiss", type=Path, default=settings.data_dir / "faces.faiss")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "frontend/public/eval/embedding_2d.json")
    parser.add_argument("--method", choices=["auto", "umap", "tsne", "pca"], default="auto")
    args = parser.parse_args()

    vectors_by_id, faiss_ntotal = _read_faiss_vectors(args.faiss)
    metadata_by_id = await _read_mysql_metadata()

    records: list[tuple[EmbeddingMeta, np.ndarray]] = []
    for embedding_id, meta in metadata_by_id.items():
        vector = vectors_by_id.get(embedding_id)
        if vector is not None:
            records.append((meta, vector))

    if not records:
        raise RuntimeError("No shared ids between MySQL face_embeddings and FAISS")

    matrix = np.stack([vec for _, vec in records], axis=0).astype(np.float32, copy=False)
    projected, method_used = _project(matrix, args.method)
    projected = _normalize(projected)

    payload = [
        {
            "x": round(float(point[0]), 6),
            "y": round(float(point[1]), 6),
            "person_id": meta.person_id,
            "name": meta.name,
            "role": meta.role,
        }
        for (meta, _), point in zip(records, projected)
    ]
    _write_json_atomic(args.out, payload)

    mysql_ids = set(metadata_by_id)
    faiss_ids = set(vectors_by_id)
    print(f"FAISS ntotal        : {faiss_ntotal}")
    print(f"MySQL embeddings    : {len(metadata_by_id)}")
    print(f"Projected points    : {len(payload)}")
    print(f"FAISS not in MySQL  : {len(faiss_ids - mysql_ids)}")
    print(f"MySQL not in FAISS  : {len(mysql_ids - faiss_ids)}")
    print(f"Projection method   : {method_used}")
    print(f"Output              : {args.out}")
    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
