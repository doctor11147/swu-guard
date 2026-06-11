"""环境自适应控制 REST API · /api/adaptive

所有配置读写走 ``system_configs`` 表，无进程内可变状态。
重启、多 worker 均安全。
"""

from __future__ import annotations

import base64
from datetime import datetime

import cv2
import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import CurrentAdmin, DbSession, forbid_guard
from app.schemas.adaptive import (
    AdaptiveConfigUpdate,
    AdaptiveDecision,
    AdaptiveStateOut,
    EvaluateRequest,
    EvaluateResponse,
)
from app.schemas.common import OkOut
from app.services.adaptive_controller import resolve_config
from app.store.models import SystemConfig

router = APIRouter(
    prefix="/adaptive",
    tags=["adaptive"],
    dependencies=[Depends(forbid_guard)],
)

# ── system_configs 读写 helper ────────────────────────────────────


async def _cfg_get(db, key: str, default=None):
    """读取 system_configs 中 adaptive.* 的值，保留原始 Python 类型。"""
    row = await db.scalar(
        select(SystemConfig.value_json).where(SystemConfig.config_key == key),
    )
    if row is None:
        return default
    return row.get("value", default)


async def _cfg_set(db, key: str, value) -> None:
    """幂等写入 system_configs。"""
    row = await db.get(SystemConfig, key)
    if row is None:
        row = SystemConfig(
            config_key=key,
            value_json={"value": value},
            description="adaptive module",
        )
        db.add(row)
    else:
        row.value_json = {"value": value}
    await db.commit()


async def _get_enabled(db) -> bool:
    v = await _cfg_get(db, "adaptive.enabled", False)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1")
    return bool(v)


async def _get_mode(db) -> str:
    enabled = await _get_enabled(db)
    if not enabled:
        return "off"
    return str(await _cfg_get(db, "adaptive.mode", "rule_only"))


# ── 构建状态响应 ──────────────────────────────────────────────────


def _build_state(
    enabled: bool,
    mode: str,
    profile: str,
    risk_level: str,
    cfg,
    reason: str,
) -> AdaptiveStateOut:
    return AdaptiveStateOut(
        enabled=enabled,
        mode=mode,  # type: ignore[arg-type]
        profile=profile,  # type: ignore[arg-type]
        risk_level=risk_level,  # type: ignore[arg-type]
        runtime_config=cfg,
        last_reason=reason,
        expires_at=datetime.now(),
        last_updated_at=datetime.now(),
    )


# ── 路由 ──────────────────────────────────────────────────────────


@router.get("/state", response_model=AdaptiveStateOut)
async def get_state(db: DbSession, _admin: CurrentAdmin):
    """返回当前自适应状态快照。大屏只读此接口。"""
    from app.services.adaptive_orchestrator import get_cached_config

    enabled = await _get_enabled(db)
    mode = await _get_mode(db)
    cfg = get_cached_config()
    return _build_state(
        enabled=enabled,
        mode=mode,
        profile=cfg.profile if cfg else "normal",
        risk_level="low",
        cfg=cfg,
        reason=cfg.reason if cfg else "default profile",
    )


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(
    payload: EvaluateRequest,
    db: DbSession,
    _admin: CurrentAdmin,
):
    """手动触发一次环境评估（仅评估，不应用）。"""
    from app.services.adaptive_orchestrator import evaluate_and_apply
    from app.services.vlm.factory import get_provider

    mode = await _get_mode(db)

    # 解析真实图像（若有），否则用灰帧
    frame_bgr = None
    if payload.image_base64:
        try:
            raw = base64.b64decode(payload.image_base64.split(",", 1)[-1])
            arr = np.frombuffer(raw, dtype=np.uint8)
            decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if decoded is not None:
                frame_bgr = decoded
        except Exception:
            pass
    if frame_bgr is None:
        frame_bgr = np.zeros((112, 112, 3), dtype=np.uint8) + 128

    # 按当前模式注入 provider + weather
    from app.services.weather_client import WeatherClient

    provider = None
    weather = None
    provider_name = str(await _cfg_get(db, "adaptive.vlm_provider", "mock"))
    weather_enabled = await _cfg_get(db, "adaptive.weather_enabled", False)
    if mode in ("vlm", "vlm_weather"):
        provider = get_provider(provider_name)
    if mode == "vlm_weather" or (payload.use_weather and bool(weather_enabled)):
        weather = WeatherClient()

    cfg = await evaluate_and_apply(
        mode=mode,  # type: ignore[arg-type]
        gate_id=payload.gate_id,
        frame_bgr=frame_bgr,
        provider=provider,  # type: ignore[arg-type]
        weather=weather,  # type: ignore[arg-type]
        db_session=db,
    )

    decision = AdaptiveDecision(
        profile=cfg.profile,
        risk_level="low",
        should_apply=True,
        action_tags=[],
        reason=cfg.reason,
        expires_in_minutes=60,
        confidence=0.5,
    )
    return EvaluateResponse(
        snapshot_id=None,
        decision=decision,
        validated_config=cfg,
        applied=False,
    )


@router.post("/apply", response_model=OkOut)
async def apply_policy(db: DbSession, _admin: CurrentAdmin):
    """将当前缓存配置写入 system_configs。仅 admin+。"""
    from app.services.adaptive_orchestrator import get_cached_config

    cfg = get_cached_config()
    if cfg is None:
        cfg = resolve_config("normal", "manual apply with no cached")
    await _cfg_set(db, "adaptive.enabled", "true")
    cur = await _cfg_get(db, "adaptive.mode", "off")
    if cur == "off":
        await _cfg_set(db, "adaptive.mode", "rule_only")
    await _cfg_set(db, "adaptive.current_profile", cfg.profile)
    await _cfg_set(db, "adaptive.last_reason", cfg.reason)
    return OkOut()


@router.get("/snapshots")
async def list_snapshots(_admin: CurrentAdmin):
    """分页返回环境快照。Phase 2 接入持久化。"""
    return {"items": [], "total": 0}


@router.get("/policies")
async def list_policies(_admin: CurrentAdmin):
    """分页返回策略审计日志。Phase 2 接入持久化。"""
    return {"items": [], "total": 0}


@router.put("/config", response_model=OkOut)
async def update_config(
    payload: AdaptiveConfigUpdate,
    db: DbSession,
    _admin: CurrentAdmin,
):
    """更新自适应模块配置，写入 system_configs，即时生效。"""
    if payload.enabled is not None:
        await _cfg_set(db, "adaptive.enabled", "true" if payload.enabled else "false")
    if payload.mode is not None:
        await _cfg_set(db, "adaptive.mode", payload.mode)
    if payload.vlm_provider is not None:
        await _cfg_set(db, "adaptive.vlm_provider", payload.vlm_provider)
    if payload.vlm_interval_seconds is not None:
        await _cfg_set(db, "adaptive.vlm_interval_seconds", str(payload.vlm_interval_seconds))
    if payload.weather_enabled is not None:
        await _cfg_set(db, "adaptive.weather_enabled", "true" if payload.weather_enabled else "false")
    return OkOut()
