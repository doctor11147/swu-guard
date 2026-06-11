"""Reusable face-image registration workflow.

This service keeps image decoding, liveness/quality gates, DB metadata writes
and FAISS updates in one place so admin-side enrollment and visitor self
enrollment cannot drift.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from anyio import to_thread
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.state import AppState
from app.store.models import FaceEmbedding, Person


class ReadableUpload(Protocol):
    async def read(self) -> bytes:
        """Return uploaded file bytes."""


@dataclass(slots=True)
class FaceRegistrationSummary:
    added: int = 0
    skipped_duplicates: int = 0
    skipped_no_face: int = 0
    skipped_spoof: int = 0
    skipped_quality: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "added": self.added,
            "skipped_duplicates": self.skipped_duplicates,
            "skipped_no_face": self.skipped_no_face,
            "skipped_spoof": self.skipped_spoof,
            "skipped_quality": self.skipped_quality,
        }


async def register_face_images(
    db: AsyncSession,
    *,
    person: Person,
    images: list[ReadableUpload],
    state: AppState,
) -> FaceRegistrationSummary:
    """Register one or more face images for an existing active person."""
    summary = FaceRegistrationSummary()
    new_vectors: list[np.ndarray] = []
    new_ids: list[int] = []

    photos_dir = Path(state.faiss.path).parent / "faces"
    photos_dir.mkdir(parents=True, exist_ok=True)
    model_name = (
        getattr(state, "settings", None) and state.settings.embedder["model_name"]
    ) or "edgeface_s_gamma_05"

    for upload in images:
        raw = await upload.read()
        if not raw:
            summary.skipped_no_face += 1
            continue

        sha = hashlib.sha256(raw).hexdigest()
        existing = await db.scalar(
            select(FaceEmbedding).where(
                FaceEmbedding.person_id == person.id,
                FaceEmbedding.sha256 == sha,
            ),
        )
        if existing is not None:
            summary.skipped_duplicates += 1
            continue

        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            summary.skipped_no_face += 1
            continue

        frame = await to_thread.run_sync(lambda: state.pipeline.process(img, max_faces=1))
        if not frame.faces or frame.faces[0].embedding is None:
            face0 = frame.faces[0] if frame.faces else None
            if face0 and face0.skipped_reason and face0.skipped_reason.startswith("anti_spoof"):
                summary.skipped_spoof += 1
            else:
                summary.skipped_no_face += 1
            continue

        face = frame.faces[0]
        emb_vec = face.embedding
        assert emb_vec is not None

        from app.core.quality import QUALITY_REGISTRATION_THRESHOLD, get_quality_assessor

        quality_score: float | None = None
        if face.aligned_112 is not None:
            quality_score = get_quality_assessor().score(face.aligned_112)
            if quality_score < QUALITY_REGISTRATION_THRESHOLD:
                summary.skipped_quality += 1
                continue

        img_path = photos_dir / (
            f"{person.id}_{sha[:12]}_{datetime.utcnow():%Y%m%dT%H%M%S}.jpg"
        )
        with open(img_path, "wb") as fh:
            fh.write(raw)

        emb = FaceEmbedding(
            person_id=person.id,
            sha256=sha,
            image_path=str(img_path),
            vector_dim=int(emb_vec.shape[0]),
            model_name=model_name,
            quality_score=quality_score,
        )
        db.add(emb)
        await db.flush()

        new_vectors.append(emb_vec.astype(np.float32, copy=False))
        new_ids.append(emb.id)
        summary.added += 1

    if new_vectors:
        with state.write_lock:
            state.faiss.add(np.stack(new_vectors, axis=0), new_ids)
            state.faiss.save()
    await db.commit()
    return summary
