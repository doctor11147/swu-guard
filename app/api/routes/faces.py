"""人脸特征 (face_embeddings) 注册路由 · /api/persons/{id}/faces

迁移自 MVP `app/api/routes_persons.py:register_person` 的注册段落，改为：
- 异步 SQLAlchemy / MySQL（沿用 P5 的 `DbSession`）
- 沿用 MVP 的 SCRFD + MiniFAS + EdgeFace 推理 pipeline（仍在 ``AppState``）
- FAISS id == ``face_embeddings.id``
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select

from app.api.deps import CurrentAdmin, DbSession, forbid_guard
from app.api.state import AppState, get_app_state
from app.schemas.common import OkOut
from app.services.face_registration import register_face_images
from app.store.models import FaceEmbedding, Person

router = APIRouter(
    prefix="/persons", tags=["faces"],
    dependencies=[Depends(forbid_guard)],
)


class FaceRegisterResponse(dict):
    """轻量响应：保留 MVP 字段语义。"""


@router.get("/{person_id}/faces")
async def list_faces(person_id: int, db: DbSession, _admin: CurrentAdmin):
    """列出某人的所有嵌入元数据（不含向量本体）。"""
    p = await db.get(Person, person_id)
    if p is None or p.deleted_at is not None:
        raise HTTPException(404, {"code": "PERSON_NOT_FOUND", "message": "人员不存在"})
    rows = await db.scalars(
        select(FaceEmbedding).where(FaceEmbedding.person_id == person_id)
        .order_by(FaceEmbedding.created_at.desc()),
    )
    return [
        {
            "id": e.id,
            "person_id": e.person_id,
            "sha256": e.sha256,
            "image_path": e.image_path,
            "vector_dim": e.vector_dim,
            "model_name": e.model_name,
            "quality_score": e.quality_score,
            "created_at": e.created_at.isoformat(),
        }
        for e in rows.all()
    ]


@router.post("/{person_id}/faces")
async def add_faces(
    person_id: int,
    db: DbSession,
    _admin: CurrentAdmin,
    images: list[UploadFile] = File(..., description="One or more face photos"),
    state: AppState = Depends(get_app_state),
):
    """对该人员新增 N 张人脸图。

    每张图通过 pipeline.process(max_faces=1) 检测+对齐+活体+嵌入；
    SHA-256 去重；仅活体通过的图会入 FAISS。
    """
    p = await db.get(Person, person_id)
    if p is None or p.deleted_at is not None:
        raise HTTPException(404, {"code": "PERSON_NOT_FOUND", "message": "人员不存在"})
    if not images:
        raise HTTPException(400, {"code": "NO_IMAGES", "message": "请上传至少一张图"})

    summary = await register_face_images(db, person=p, images=images, state=state)
    return summary.to_dict()


@router.delete("/{person_id}/faces/{face_id}", response_model=OkOut)
async def delete_face(
    person_id: int,
    face_id: int,
    db: DbSession,
    _admin: CurrentAdmin,
    state: AppState = Depends(get_app_state),
):
    e = await db.get(FaceEmbedding, face_id)
    if e is None or e.person_id != person_id:
        raise HTTPException(404, {"code": "FACE_NOT_FOUND", "message": "嵌入不存在"})
    with state.write_lock:
        state.faiss.remove([face_id])
        state.faiss.save()
    await db.delete(e)
    await db.commit()
    return OkOut()
