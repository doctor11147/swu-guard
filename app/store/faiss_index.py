# mypy: disable-error-code="attr-defined"
"""FAISS-backed 1:N vector store.

Design
------
- Embeddings are L2-normalised upstream (see `core.embedder`), so cosine
  similarity == inner product. We use `IndexFlatIP` for exact search (no
  recall loss) wrapped in `IndexIDMap2` so each vector carries the
  embedding-row primary key from SQLite.
- `IndexFlatIP` does not support `remove_ids`. To delete, we use
  `IndexIDMap2` which does (via underlying id map). We avoid `IndexIDMap`
  because that variant does not support remove on flat indices either; the
  v2 variant + flat is the supported combination as of FAISS 1.8.
- Persistence: a single `.faiss` file. Atomic save via tmp+rename.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple, Sequence

import faiss
import numpy as np


class SearchHit(NamedTuple):
    embedding_id: int   # the id we attached when adding (== embeddings.id in DB)
    score: float        # cosine similarity in [-1, 1]


class FaissStore:
    def __init__(self, dim: int, index_path: str | Path):
        self.dim = int(dim)
        self.path = Path(index_path)
        if self.path.exists():
            idx = faiss.read_index(str(self.path))
            if idx.d != self.dim:
                raise ValueError(f"index dim {idx.d} != configured dim {self.dim}")
            self._index = idx
        else:
            self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(self.dim))

    @property
    def size(self) -> int:
        return int(self._index.ntotal)

    def _validate(self, vectors: np.ndarray, ids: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32, copy=False)
        if vectors.ndim != 2 or vectors.shape[1] != self.dim:
            raise ValueError(f"expected (N,{self.dim}) float32, got {vectors.shape} {vectors.dtype}")
        if len(ids) != vectors.shape[0]:
            raise ValueError("ids length must match vectors")
        return np.ascontiguousarray(vectors), np.asarray(ids, dtype=np.int64)

    def add(self, vectors: np.ndarray, ids: Sequence[int]) -> None:
        v, i = self._validate(vectors, ids)
        self._index.add_with_ids(v, i)

    def remove(self, ids: Sequence[int]) -> int:
        sel = faiss.IDSelectorBatch(np.asarray(ids, dtype=np.int64))
        return int(self._index.remove_ids(sel))

    def search(self, query: np.ndarray, top_k: int = 5) -> list[list[SearchHit]]:
        if query.dtype != np.float32:
            query = query.astype(np.float32, copy=False)
        if query.ndim == 1:
            query = query.reshape(1, -1)
        if query.shape[1] != self.dim:
            raise ValueError(f"query dim {query.shape[1]} != {self.dim}")
        if self.size == 0:
            return [[] for _ in range(query.shape[0])]
        scores, ids = self._index.search(np.ascontiguousarray(query), top_k)
        out: list[list[SearchHit]] = []
        for row_scores, row_ids in zip(scores, ids):
            hits = [SearchHit(int(i), float(s)) for i, s in zip(row_ids, row_scores) if i != -1]
            out.append(hits)
        return out

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        faiss.write_index(self._index, str(tmp))
        os.replace(tmp, self.path)
