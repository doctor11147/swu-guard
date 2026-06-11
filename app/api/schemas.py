"""Pydantic schemas. Kept apart from SQLAlchemy models so wire format
and storage can evolve independently.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PersonOut(BaseModel):
    id: int
    student_id: str
    name: str
    note: Optional[str] = None
    embedding_count: int
    created_at: datetime


class RegisterResponse(BaseModel):
    person: PersonOut
    embeddings_added: int
    skipped_duplicates: int
    skipped_no_face: int
    skipped_spoof: int


class MatchOut(BaseModel):
    person_id: int
    student_id: str
    name: str
    score: float = Field(..., description="cosine similarity in [-1, 1]")


class FaceOut(BaseModel):
    bbox: list[float]   # [x1, y1, x2, y2]
    score: float        # detection confidence
    spoof_score: Optional[float] = None
    is_real: Optional[bool] = None
    decision: str       # 'granted' | 'rejected' | 'spoof'
    match: Optional[MatchOut] = None


class RecognizeResponse(BaseModel):
    faces: list[FaceOut]
    threshold: float


class ThresholdUpdate(BaseModel):
    match_threshold: Optional[float] = Field(None, ge=-1.0, le=1.0)
    real_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)


class ThresholdOut(BaseModel):
    match_threshold: float
    real_threshold: float
    anti_spoof_enabled: bool
