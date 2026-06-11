"""Seed projection/demo face data from local identity-organized datasets.

The script is intentionally additive and idempotent:
- it never deletes or rewrites existing persons/embeddings;
- generated identities use deterministic, schema-valid external ids;
- duplicate face photos are skipped by (person_id, sha256), matching the app.

Default source: datasets/VGGFace2/train, where each directory is one identity.
Offline dataset photos are not live camera frames, so liveness is skipped by
default while keeping the normal detector -> aligner -> embedder -> quality
pipeline. Pass --run-anti-spoof to enforce liveness if desired.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import selectinload

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.pipeline import build_default_pipeline
from app.core.quality import QUALITY_REGISTRATION_THRESHOLD, get_quality_assessor
from app.schemas.persons import PersonCreateIn
from app.services.persons import create_person
from app.settings import Settings
from app.store.faiss_index import FaissStore
from app.store.models import College, FaceEmbedding, Person
from app.store.session import db_session

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
DORM_ZONES = ["nan", "zhu", "mei", "li", "ju", "tao", "xing"]
ROLE_WEIGHTS = [
    ("student", 50),
    ("graduate", 25),
    ("teacher", 20),
    ("staff", 15),
    ("visitor", 10),
]
MAJORS = [
    "Computer Science",
    "Artificial Intelligence",
    "Information Security",
    "Software Engineering",
    "Data Science",
    "Automation",
    "Mathematics",
    "Physics",
    "Chemistry",
    "Biology",
    "Education",
    "Psychology",
]
SEED_CREATED_AT = datetime(2026, 1, 1, 0, 0, 0)


@dataclass(slots=True)
class PreparedFace:
    raw: bytes
    sha256: str
    vector: np.ndarray
    quality_score: float | None
    source_path: Path


@dataclass(slots=True)
class SeedStats:
    people_target: int = 0
    people_created: int = 0
    people_existing: int = 0
    people_with_new_faces: int = 0
    faces_added: int = 0
    skipped_duplicates: int = 0
    skipped_no_face: int = 0
    skipped_spoof: int = 0
    skipped_quality: int = 0
    skipped_decode: int = 0
    skipped_identity_no_valid_face: int = 0


def _role_plan(limit: int) -> list[str]:
    weighted = [role for role, count in ROLE_WEIGHTS for _ in range(count)]
    if limit <= len(weighted):
        return weighted[:limit]
    return [weighted[i % len(weighted)] for i in range(limit)]


def _image_files(identity_dir: Path, *, seed: int, limit: int) -> list[Path]:
    files = [
        p for p in identity_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]
    rng = random.Random(f"{seed}:{identity_dir.name}")
    rng.shuffle(files)
    return files[:limit]


def _identity_dirs(source_dir: Path, *, seed: int) -> list[Path]:
    dirs = [
        p for p in source_dir.iterdir()
        if p.is_dir() and any(
            child.is_file() and child.suffix.lower() in IMAGE_EXTS
            for child in p.iterdir()
        )
    ]
    rng = random.Random(seed)
    rng.shuffle(dirs)
    return dirs


def _college_code(college: College | None) -> str:
    code = str(college.code if college is not None else "999")
    digits = "".join(ch for ch in code if ch.isdigit())
    return (digits or "999").zfill(3)[-3:]


def _external_id(role: str, ordinal: int, college: College | None) -> str:
    year = 2026
    code = _college_code(college)
    if role == "student":
        class_no = ((ordinal - 1) % 80) + 1
        seq_no = ((ordinal - 1) % 900) + 1
        return f"22{year}{code}{class_no:03d}{seq_no:03d}"
    if role == "graduate":
        return f"23{year}{code}{ordinal:04d}"
    if role == "teacher":
        return f"T{year % 100:02d}{ordinal:04d}"
    if role == "staff":
        return f"W{year % 100:02d}{ordinal:04d}"

    month = ((ordinal - 1) % 12) + 1
    day = ((ordinal - 1) % 28) + 1
    checks = "0123456789X"
    return f"5101001988{month:02d}{day:02d}{ordinal:03d}{checks[ordinal % len(checks)]}"


def _payload_for(
    *,
    role: str,
    ordinal: int,
    source_identity: str,
    college: College | None,
) -> PersonCreateIn:
    is_student_like = role in {"student", "graduate"}
    return PersonCreateIn(
        external_id=_external_id(role, ordinal, college),
        name=f"Dataset {role.title()} {ordinal:03d}",
        role=role,  # type: ignore[arg-type]
        college_id=college.id if college is not None and role != "visitor" else None,
        major=MAJORS[(ordinal - 1) % len(MAJORS)] if role in {"student", "graduate"} else None,
        class_code=f"2026-{((ordinal - 1) % 12) + 1:02d}" if role == "student" else None,
        enrollment_year=2026 if is_student_like else None,
        campus="beibei" if ordinal % 5 else "rongchang",
        dorm_zone=DORM_ZONES[(ordinal - 1) % len(DORM_ZONES)] if is_student_like else None,
        email=f"seed-{role}-{ordinal:03d}@example.invalid",
        note=f"seed:embedding_projection dataset=VGGFace2 identity={source_identity}",
    )


async def _existing_hashes(session, person_id: int) -> set[str]:
    rows = await session.scalars(
        select(FaceEmbedding.sha256).where(FaceEmbedding.person_id == person_id),
    )
    return set(rows.all())


def _decode(raw: bytes) -> np.ndarray | None:
    arr = np.frombuffer(raw, dtype=np.uint8)
    if arr.size == 0:
        return None
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _prepare_faces(
    *,
    image_paths: Sequence[Path],
    pipeline,
    skip_anti_spoof: bool,
    existing_hashes: set[str],
    stats: SeedStats,
) -> list[PreparedFace]:
    prepared: list[PreparedFace] = []
    quality = get_quality_assessor()

    for path in image_paths:
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if sha in existing_hashes:
            stats.skipped_duplicates += 1
            continue

        img = _decode(raw)
        if img is None:
            stats.skipped_decode += 1
            continue

        frame = pipeline.process(
            img,
            max_faces=1,
            skip_anti_spoof=skip_anti_spoof,
        )
        if not frame.faces:
            stats.skipped_no_face += 1
            continue

        face = frame.faces[0]
        if face.embedding is None:
            if face.skipped_reason and face.skipped_reason.startswith("anti_spoof"):
                stats.skipped_spoof += 1
            else:
                stats.skipped_no_face += 1
            continue

        quality_score: float | None = None
        if face.aligned_112 is not None:
            quality_score = quality.score(face.aligned_112)
            if quality_score < QUALITY_REGISTRATION_THRESHOLD:
                stats.skipped_quality += 1
                continue

        prepared.append(
            PreparedFace(
                raw=raw,
                sha256=sha,
                vector=face.embedding.astype(np.float32, copy=False),
                quality_score=quality_score,
                source_path=path,
            ),
        )
        existing_hashes.add(sha)

    return prepared


async def _active_colleges(session) -> list[College]:
    rows = await session.scalars(
        select(College)
        .options(selectinload(College.faculty))
        .where(College.is_active.is_(True))
        .order_by(College.id),
    )
    return list(rows.all())


async def _seed(args: argparse.Namespace) -> SeedStats:
    settings = Settings.load()
    source_dir = Path(args.source_dir).expanduser().resolve()
    if not source_dir.exists():
        raise FileNotFoundError(f"dataset source not found: {source_dir}")

    identity_dirs = _identity_dirs(source_dir, seed=args.seed)
    if not identity_dirs:
        raise RuntimeError(f"no identity directories with images under {source_dir}")

    pipeline = build_default_pipeline(settings)
    faiss = FaissStore(dim=pipeline.embedding_dim, index_path=settings.data_dir / "faces.faiss")
    photos_dir = settings.data_dir / "faces"
    photos_dir.mkdir(parents=True, exist_ok=True)
    model_name = settings.embedder["model_name"]

    stats = SeedStats(people_target=int(args.people))
    roles = _role_plan(int(args.people))
    role_ordinals = {role: 0 for role, _ in ROLE_WEIGHTS}
    people_done = 0

    async with db_session() as session:
        colleges = await _active_colleges(session)

        for identity_dir in identity_dirs:
            if people_done >= args.people:
                break

            role = roles[people_done]
            role_ordinals[role] += 1
            ordinal = role_ordinals[role]
            college = colleges[(people_done + ordinal) % len(colleges)] if colleges else None
            payload = _payload_for(
                role=role,
                ordinal=ordinal,
                source_identity=identity_dir.name,
                college=college,
            )

            person = await session.scalar(
                select(Person).where(Person.external_id == payload.external_id),
            )
            if person is not None and person.deleted_at is not None:
                continue

            created = person is None
            existing = await _existing_hashes(session, person.id) if person is not None else set()
            image_paths = _image_files(identity_dir, seed=args.seed, limit=args.images_per_person)
            prepared = _prepare_faces(
                image_paths=image_paths,
                pipeline=pipeline,
                skip_anti_spoof=not args.run_anti_spoof,
                existing_hashes=existing,
                stats=stats,
            )

            if not prepared and created:
                stats.skipped_identity_no_valid_face += 1
                continue
            elif not prepared:
                stats.people_existing += 1
                people_done += 1
                continue

            if person is None:
                person = await create_person(session, payload)
                person.created_at = SEED_CREATED_AT
                person.updated_at = SEED_CREATED_AT

            new_vectors: list[np.ndarray] = []
            new_ids: list[int] = []
            for face in prepared:
                img_path = photos_dir / (
                    f"{person.id}_{face.sha256[:12]}_{datetime.utcnow():%Y%m%dT%H%M%S}.jpg"
                )
                with open(img_path, "wb") as fh:
                    fh.write(face.raw)

                emb = FaceEmbedding(
                    person_id=person.id,
                    sha256=face.sha256,
                    image_path=str(img_path),
                    vector_dim=int(face.vector.shape[0]),
                    model_name=model_name,
                    quality_score=face.quality_score,
                    created_at=SEED_CREATED_AT,
                )
                session.add(emb)
                await session.flush()
                new_vectors.append(face.vector)
                new_ids.append(int(emb.id))

            if new_vectors:
                faiss.add(np.stack(new_vectors, axis=0), new_ids)
                faiss.save()
                stats.faces_added += len(new_vectors)
                stats.people_with_new_faces += 1

            await session.commit()
            stats.people_created += int(created)
            stats.people_existing += int(not created)
            people_done += 1

            if people_done % 10 == 0:
                print(
                    f"seeded_people={people_done} "
                    f"created={stats.people_created} faces_added={stats.faces_added}",
                    flush=True,
                )

    return stats


def _default_source_dir() -> Path:
    root = PROJECT_ROOT / "datasets"
    preferred = root / "VGGFace2" / "train"
    return preferred if preferred.exists() else root


async def _amain() -> int:
    parser = argparse.ArgumentParser(description="Seed 100+ projection identities from local datasets")
    parser.add_argument("--source-dir", type=Path, default=_default_source_dir())
    parser.add_argument("--people", type=int, default=120)
    parser.add_argument("--images-per-person", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260610)
    parser.add_argument("--run-anti-spoof", action="store_true")
    args = parser.parse_args()

    if args.people < 1:
        raise ValueError("--people must be positive")
    if args.images_per_person < 1:
        raise ValueError("--images-per-person must be positive")

    print(f"source_dir        : {Path(args.source_dir).expanduser().resolve()}")
    print(f"target_people     : {args.people}")
    print(f"images_per_person : {args.images_per_person}")
    print(f"liveness_gate     : {'enabled' if args.run_anti_spoof else 'skipped for offline dataset'}")

    stats = await _seed(args)
    print("===== seed summary =====")
    for key, value in asdict(stats).items():
        print(f"{key:30s}: {value}")
    if stats.people_created + stats.people_existing < args.people:
        print("WARNING: fewer identities were processed than requested")
        return 2
    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
