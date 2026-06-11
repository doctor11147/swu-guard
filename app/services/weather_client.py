"""Open-Meteo weather client — weak evidence only.

Uses ``http.client`` (stdlib) to avoid ``httpx`` TLS issues on macOS.
The sync HTTP call is offloaded via ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import http.client
import json
from urllib.parse import urlencode

from app.schemas.adaptive import WeatherEvidence

OPEN_METEO_HOST = "api.open-meteo.com"
TIMEOUT = 5.0


def _fetch_sync(lat: float, lon: float, timeout: float) -> WeatherEvidence:
    """Synchronous Open-Meteo fetch via http.client."""
    params = urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "cloud_cover,precipitation,weather_code,is_day,relative_humidity_2m",
        "hourly": "visibility,direct_normal_irradiance",
        "timezone": "Asia/Shanghai",
        "forecast_hours": "1",
    })
    try:
        conn = http.client.HTTPSConnection(OPEN_METEO_HOST, timeout=timeout)
        conn.request("GET", f"/v1/forecast?{params}")
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        conn.close()
        if resp.status != 200:
            return WeatherEvidence(provider="open_meteo_unavailable")
        data = json.loads(raw)
    except Exception:
        return WeatherEvidence(provider="open_meteo_unavailable")

    try:
        cur = data.get("current", {}) or {}
        hourly = data.get("hourly", {}) or {}
        vis_arr = hourly.get("visibility", [])
        irr_arr = hourly.get("direct_normal_irradiance", [])

        return WeatherEvidence(
            provider="open_meteo",
            cloud_pct=cur.get("cloud_cover"),
            visibility_km=float(vis_arr[0]) / 1000.0 if vis_arr else None,
            precipitation_mm=cur.get("precipitation"),
            irradiance=float(irr_arr[0]) if irr_arr else None,
            humidity_pct=cur.get("relative_humidity_2m"),
            is_day=bool(cur.get("is_day")) if cur.get("is_day") is not None else None,
            raw=data,
        )
    except Exception:
        return WeatherEvidence(provider="open_meteo_parse_error")


class WeatherClient:
    """Async Open-Meteo client.  The sync ``http.client`` call runs on a thread."""

    def __init__(self, timeout: float = TIMEOUT) -> None:
        self._timeout = timeout

    async def fetch(self, lat: float, lon: float) -> WeatherEvidence:
        return await asyncio.to_thread(_fetch_sync, lat, lon, self._timeout)
