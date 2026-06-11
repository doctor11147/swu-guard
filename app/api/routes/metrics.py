"""Lightweight in-process recognition metrics.

This endpoint intentionally avoids external dependencies so observability can be
enabled in the existing conda environment. Data is best-effort and resets when
the API process restarts.
"""
from __future__ import annotations

from collections import Counter, deque
from statistics import mean
from threading import Lock
from typing import Annotated, Iterable, Mapping

from fastapi import APIRouter, Query

router = APIRouter(tags=["metrics"])

STAGES = ("detect", "align", "liveness", "quality", "embed", "retrieve", "total")
MAX_SAMPLES = 512

_samples: deque[dict[str, float]] = deque(maxlen=MAX_SAMPLES)
_decisions: Counter[str] = Counter()
_lock = Lock()


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return round(max(0.0, number), 3)


def _percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * ratio + 0.999999) - 1))
    return round(ordered[index], 3)


def _stage_stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "avg": None, "p50": None, "p95": None, "max": None}
    return {
        "count": len(values),
        "avg": round(mean(values), 3),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "max": round(max(values), 3),
    }


def record_recognition_metrics(
    timing: Mapping[str, float] | None,
    decisions: Iterable[str],
) -> None:
    """Record one recognition response without affecting the request path."""
    try:
        cleaned: dict[str, float] = {}
        if timing:
            for stage in STAGES:
                value = _finite_float(timing.get(stage))
                if value is not None:
                    cleaned[stage] = value

        decision_list = [str(decision) for decision in decisions if decision]
        with _lock:
            if cleaned:
                _samples.append(cleaned)
            _decisions.update(decision_list)
    except Exception:
        # Metrics are observability-only; never fail recognition.
        pass


@router.get("/metrics")
def get_metrics(limit: Annotated[int, Query(ge=1, le=MAX_SAMPLES)] = 120):
    """Return recent recognition timing aggregates and decision counters."""
    with _lock:
        rows = list(_samples)[-limit:]
        decisions = dict(_decisions)

    return {
        "sample_count": len(rows),
        "window_limit": limit,
        "stages": {
            stage: _stage_stats([
                row[stage] for row in rows
                if stage in row and _finite_float(row[stage]) is not None
            ])
            for stage in STAGES
        },
        "decisions": decisions,
    }
