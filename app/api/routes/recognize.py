"""识别路由 · /api/recognize（图像）+ /api/ws/recognize（视频流）。

- 1:N 余弦匹配：阈值从 ``system_configs.recognition.match_threshold`` 读取，
  支持 ``system_configs PUT`` 后下次请求即生效。
- 通行结果写入 ``access_logs``。
"""
from __future__ import annotations

import asyncio
import base64
import json
import time

import cv2
import numpy as np
from anyio import to_thread
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession
from app.api.state import AppState, get_app_state
from app.core.pipeline import FaceRecord, FrameResult
from app.api.routes.metrics import record_recognition_metrics
from app.services.system import get_config_value
from app.store.models import AccessLog, FaceEmbedding, Gate, Person
from app.store.session import get_session_factory

router = APIRouter(tags=["recognize"])

TIMING_STAGES = ("detect", "align", "liveness", "quality", "embed", "retrieve")


def _timer_start() -> float | None:
    try:
        return time.perf_counter()
    except Exception:
        return None


def _add_elapsed(timing_acc: dict[str, float] | None, stage: str, started: float | None) -> None:
    if timing_acc is None or started is None:
        return
    try:
        timing_acc[stage] = timing_acc.get(stage, 0.0) + (time.perf_counter() - started) * 1000.0
    except Exception:
        # Timing is observability-only; never affect recognition.
        pass


def _build_timing(
    frame: FrameResult,
    route_timing: dict[str, float],
    started: float | None,
) -> dict[str, float]:
    timing: dict[str, float] = {}
    frame_timing = frame.timing or {}
    for stage in TIMING_STAGES:
        value = route_timing.get(stage, frame_timing.get(stage, 0.0))
        try:
            timing[stage] = round(max(0.0, float(value)), 3)
        except Exception:
            timing[stage] = 0.0
    try:
        total = (time.perf_counter() - started) * 1000.0 if started is not None else sum(timing.values())
    except Exception:
        total = sum(timing.values())
    timing["total"] = round(max(0.0, float(total)), 3)
    return timing

# ── 环境自适应集成 ─────────────────────────────────────────────────


async def _get_adaptive_cfg(db, frame_bgr):
    """读取当前自适应模式 + runtime config。失败时回退到 normal 基准。

    识别请求必须保持低延迟：VLM/weather 模式只读取已有缓存，不在用户点击
    "开始识别"时同步发起外部模型或天气请求。手动评估页负责刷新该缓存。
    """
    try:
        mode_val = await get_config_value(db, "adaptive.mode", "off")
        enabled_val = await get_config_value(db, "adaptive.enabled", False)
        if mode_val == "off" or not bool(enabled_val):
            return None
        if mode_val in ("vlm", "vlm_weather"):
            from app.services.adaptive_orchestrator import get_cached_config

            return get_cached_config()

        from app.services.adaptive_orchestrator import get_runtime_config

        return await get_runtime_config(
            mode=mode_val,  # type: ignore[arg-type]
            frame_bgr=frame_bgr,
            provider=None,
            weather=None,
            db_session=db,
        )
    except Exception:
        return None


def _adaptive_enrich(result: dict, cfg) -> dict:
    """将 adaptive 上下文嵌入识别结果 JSON。"""
    if cfg is None:
        return result
    result["adaptive_profile"] = cfg.profile
    result["adaptive_reason"] = cfg.reason
    result["runtime_thresholds"] = {
        "det_thresh": cfg.det_thresh,
        "spoof_thresh": cfg.spoof_thresh,
        "match_thresh": cfg.match_thresh,
        "quality_thresh": cfg.quality_thresh,
        "consensus_frames": cfg.consensus_frames,
    }
    return result


async def _resolve_match(
    db: AsyncSession, embedding_id: int,
) -> tuple[Person | None, str | None]:
    """通过 face_embeddings.id 反查 Person。"""
    row = (await db.execute(
        select(Person, Person.external_id)
        .join(FaceEmbedding, FaceEmbedding.person_id == Person.id)
        .where(FaceEmbedding.id == embedding_id),
    )).first()
    if row is None:
        return None, None
    p, ext = row
    return p, ext


async def _decide_face(
    db: AsyncSession,
    face: FaceRecord,
    state: AppState,
    threshold: float,
    timing_acc: dict[str, float] | None = None,
) -> dict:
    """单张人脸 → decision JSON（含质量门控加权）。"""
    bbox = face.detection.bbox.tolist()
    score = float(face.detection.score)
    spoof_score = face.spoof.real_score if face.spoof else None
    is_real = face.spoof.is_real if face.spoof else None

    # 质量评估：低质量人脸提高匹配阈值
    quality_score: float | None = None
    effective_threshold = threshold
    if face.aligned_112 is not None:
        started = _timer_start()
        try:
            from app.core.quality import (
                QUALITY_LOW_THRESHOLD,
                QUALITY_MATCH_PENALTY,
                get_quality_assessor,
            )
            quality_score = get_quality_assessor().score(face.aligned_112)
            if quality_score < QUALITY_LOW_THRESHOLD:
                effective_threshold = threshold + QUALITY_MATCH_PENALTY
        except Exception:
            pass  # 质量评估失败不影响识别主线
        finally:
            _add_elapsed(timing_acc, "quality", started)

    base_payload: dict = {
        "bbox": bbox,
        "score": score,
        "spoof_score": spoof_score,
        "is_real": is_real,
        "kps": face.detection.kps.tolist(),
    }
    if quality_score is not None:
        base_payload["quality_score"] = quality_score
        if effective_threshold != threshold:
            base_payload["quality_adjusted_threshold"] = effective_threshold

    # spoof 直接拒
    if face.skipped_reason and face.skipped_reason.startswith("anti_spoof"):
        return {
            **base_payload,
            "decision": "spoof", "match": None,
        }
    if face.embedding is None:
        return {
            **base_payload,
            "decision": "no_face", "match": None,
        }

    started = _timer_start()
    hits = state.faiss.search(face.embedding, top_k=1)[0]
    _add_elapsed(timing_acc, "retrieve", started)
    if not hits:
        return {
            **base_payload,
            "decision": "rejected", "match": None,
        }
    top = hits[0]
    matched_person, ext_id = await _resolve_match(db, top.embedding_id)

    # 孤儿向量兜底：FAISS 命中但 MySQL 找不到对应 Person
    # （例如 MVP 时代写入的向量、或软删除后 FAISS 没及时清理）。
    # 不能返回 granted，否则前端会显示 "undefined · undefined"。
    if matched_person is None:
        return {
            **base_payload,
            "decision": "rejected", "match": None,
            "detail": f"orphan_vector(faiss_id={top.embedding_id})",
        }

    match_payload = {
        "person_id": matched_person.id, "student_id": ext_id,
        "name": matched_person.name, "score": float(top.score),
    }
    decision = "granted" if top.score >= effective_threshold else "rejected"

    # 访客预约校验：通过匹配的 person 检查是否有有效预约
    visitor_appointment_id = None
    if decision == "granted" and matched_person.role == "visitor":
        from app.services.visitors import check_valid_appointment
        valid_apt = await check_valid_appointment(db, person_id=matched_person.id)
        if valid_apt is None:
            decision = "rejected"
            match_payload = {**match_payload, "detail": "no_valid_appointment"}
        else:
            visitor_appointment_id = valid_apt.id
            match_payload = {**match_payload, "visitor_appointment_id": valid_apt.id}

    result: dict = {
        **base_payload,
        "decision": decision,
        "match": match_payload if decision == "granted" else (
            match_payload if decision == "rejected" else None
        ),
        "visitor_appointment_id": visitor_appointment_id,
    }
    return result


async def _log_access(
    db: AsyncSession, *, decision: str, score: float | None,
    spoof_score: float | None, person_id: int | None, gate_id: int | None,
    detail: str | None = None,
) -> None:
    db.add(AccessLog(
        decision=decision, score=score, spoof_score=spoof_score,
        matched_person_id=person_id, gate_id=gate_id, detail=detail,
    ))
    await db.commit()


async def _resolve_gate_id(
    db: AsyncSession,
    gate_code: str | None,
    gate_id: int | None = None,
) -> int | None:
    if gate_id is not None:
        return gate_id if await db.get(Gate, gate_id) is not None else None
    if not gate_code:
        return None
    return await db.scalar(select(Gate.id).where(Gate.code == gate_code))


@router.post("/recognize")
async def recognize(
    db: DbSession,
    image: UploadFile = File(...),
    gate_code: str | None = None,
    gate_id: int | None = None,
    state: AppState = Depends(get_app_state),
):
    raw = await image.read()
    if not raw:
        raise HTTPException(400, {"code": "EMPTY_IMAGE", "message": "空图像"})
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, {"code": "DECODE_FAILED", "message": "无法解码图像"})

    # 自适应 runtime config（规则 / VLM / off）
    adaptive_cfg = await _get_adaptive_cfg(db, img)
    if adaptive_cfg is not None:
        threshold = adaptive_cfg.match_thresh
    else:
        threshold = float(await get_config_value(db, "recognition.match_threshold", 0.40))

    timing_started = _timer_start()
    route_timing: dict[str, float] = {}
    frame = await to_thread.run_sync(
        lambda: state.pipeline.process(img, max_faces=1, collect_timing=True),
    )

    out_faces = []
    for face in frame.faces:
        face_out = await _decide_face(db, face, state, threshold, route_timing)

        # 安全控制器：manual_review / auto_grant_enabled 可覆盖 decision
        if adaptive_cfg is not None:
            if adaptive_cfg.manual_review and face_out.get("decision") == "granted":
                face_out["decision"] = "rejected"
                face_out["detail"] = "manual_review(adaptive)"
            elif not adaptive_cfg.auto_grant_enabled and face_out.get("decision") == "granted":
                face_out["decision"] = "rejected"
                face_out["detail"] = "auto_grant_disabled(adaptive)"

        _adaptive_enrich(face_out, adaptive_cfg)
        out_faces.append(face_out)

    timing = _build_timing(frame, route_timing, timing_started)
    resolved_gate_id = await _resolve_gate_id(db, gate_code, gate_id)
    for face_out in out_faces:
        # 写日志（含 adaptive 字段）
        log = AccessLog(
            decision=face_out["decision"],
            score=(face_out["match"]["score"] if face_out.get("match") else None),
            spoof_score=face_out["spoof_score"],
            matched_person_id=(face_out["match"]["person_id"] if face_out.get("match") and face_out["decision"] == "granted" else None),
            visitor_appointment_id=face_out.get("visitor_appointment_id"),
            gate_id=resolved_gate_id,
            adaptive_profile=adaptive_cfg.profile if adaptive_cfg else None,
            adaptive_reason=adaptive_cfg.reason if adaptive_cfg else None,
            runtime_thresholds={
                "det_thresh": adaptive_cfg.det_thresh,
                "spoof_thresh": adaptive_cfg.spoof_thresh,
                "match_thresh": adaptive_cfg.match_thresh,
                "quality_thresh": adaptive_cfg.quality_thresh,
                "consensus_frames": adaptive_cfg.consensus_frames,
            } if adaptive_cfg else None,
        )
        db.add(log)

    await db.commit()
    decisions = [str(face.get("decision")) for face in out_faces] or ["no_face"]
    record_recognition_metrics(
        timing,
        decisions,
    )

    result = {"faces": out_faces, "threshold": threshold, "timing": timing}
    _adaptive_enrich(result, adaptive_cfg)
    return result


@router.websocket("/ws/recognize")
async def ws_recognize(ws: WebSocket):
    """流式识别：客户端发 base64-JPEG 帧，服务端回 JSON。

    认证：开发期允许匿名（前端摄像头流）；生产可在 query string 带 token。
    实测每帧 ~200ms（CPU），客户端建议 5–10 fps 节流。
    """
    await ws.accept()
    state: AppState = ws.app.state.app_state
    SessionLocal = get_session_factory()
    try:
        while True:
            msg = await ws.receive_text()
            try:
                payload = json.loads(msg)
                b64 = payload["image"]
                gate_code = payload.get("gate_code")
                if "," in b64:
                    b64 = b64.split(",", 1)[1]
                raw = base64.b64decode(b64)
            except Exception as e:
                await ws.send_json({"error": f"bad payload: {e}"})
                continue
            arr = np.frombuffer(raw, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                await ws.send_json({"error": "decode failed"})
                continue

            async with SessionLocal() as db:
                # 自适应 runtime config
                adaptive_cfg = await _get_adaptive_cfg(db, img)
                if adaptive_cfg is not None:
                    threshold = adaptive_cfg.match_thresh
                else:
                    threshold = float(await get_config_value(db, "recognition.match_threshold", 0.40))

                timing_started = _timer_start()
                route_timing: dict[str, float] = {}
                frame: FrameResult = await asyncio.to_thread(
                    state.pipeline.process, img, 1, False, True,
                )
                out_faces = []
                for face in frame.faces:
                    face_out = await _decide_face(db, face, state, threshold, route_timing)
                    # manual_review / auto_grant 覆盖
                    if adaptive_cfg is not None:
                        if adaptive_cfg.manual_review and face_out.get("decision") == "granted":
                            face_out["decision"] = "rejected"
                            face_out["detail"] = "manual_review(adaptive)"
                        elif not adaptive_cfg.auto_grant_enabled and face_out.get("decision") == "granted":
                            face_out["decision"] = "rejected"
                            face_out["detail"] = "auto_grant_disabled(adaptive)"
                    _adaptive_enrich(face_out, adaptive_cfg)
                    out_faces.append(face_out)

                timing = _build_timing(frame, route_timing, timing_started)
                gate_id = await _resolve_gate_id(db, gate_code)
                decisions = [str(face.get("decision")) for face in out_faces] or ["no_face"]
                record_recognition_metrics(
                    timing,
                    decisions,
                )
                response = {
                    "faces": out_faces,
                    "threshold": threshold,
                    "gate_id": gate_id,
                    "timing": timing,
                }
                _adaptive_enrich(response, adaptive_cfg)
                await ws.send_json(response)
    except WebSocketDisconnect:
        return
