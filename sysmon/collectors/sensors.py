"""Battery and temperature sensors (opt-in)."""

from __future__ import annotations

import math
from typing import Any

import psutil


def get_sensors_info() -> dict[str, Any]:
    """Return battery and temperature readings when the OS exposes them."""
    battery: dict[str, Any] | None = None
    try:
        reading = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    except Exception:
        reading = None
    if reading is not None:
        percent_raw = getattr(reading, "percent", None)
        if (
            isinstance(percent_raw, bool)
            or not isinstance(percent_raw, (int, float))
            or not math.isfinite(percent_raw)
        ):
            percent = None
        else:
            percent = float(percent_raw)
        secsleft = getattr(reading, "secsleft", None)
        unlimited = getattr(psutil, "POWER_TIME_UNLIMITED", -1)
        unknown = getattr(psutil, "POWER_TIME_UNKNOWN", -2)
        if (
            secsleft in (None, unlimited, unknown)
            or isinstance(secsleft, bool)
            or not isinstance(secsleft, (int, float))
            or not math.isfinite(secsleft)
            or secsleft < 0
        ):
            remaining = None
        else:
            remaining = int(secsleft)
        battery = {
            "percent": percent,
            "secsleft": remaining,
            "power_plugged": bool(getattr(reading, "power_plugged", False)),
        }

    temperatures: dict[str, list[dict[str, Any]]] = {}
    try:
        grouped = (
            psutil.sensors_temperatures()
            if hasattr(psutil, "sensors_temperatures")
            else None
        ) or {}
    except Exception:
        grouped = {}
    if not isinstance(grouped, dict):
        grouped = {}
    for name, entries in grouped.items():
        if not isinstance(entries, list):
            continue
        rows: list[dict[str, Any]] = []
        for entry in entries:
            current_raw = getattr(entry, "current", None)
            if (
                isinstance(current_raw, bool)
                or not isinstance(current_raw, (int, float))
                or not math.isfinite(current_raw)
            ):
                current = None
            else:
                current = float(current_raw)
            rows.append(
                {
                    "label": str(getattr(entry, "label", "") or ""),
                    "current": current,
                    "high": getattr(entry, "high", None),
                    "critical": getattr(entry, "critical", None),
                }
            )
        temperatures[str(name)] = rows
    return {"battery": battery, "temperatures": temperatures}


def hottest_temperature(info: dict[str, Any]) -> tuple[float, dict[str, Any]] | None:
    """Return the highest numeric temperature reading and its entry."""
    temperatures = info.get("temperatures") if isinstance(info, dict) else None
    if not isinstance(temperatures, dict):
        return None
    best: tuple[float, dict[str, Any]] | None = None
    for entries in temperatures.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            current = entry.get("current")
            if isinstance(current, bool) or not isinstance(current, (int, float)):
                continue
            if not math.isfinite(current):
                continue
            reading = float(current)
            if best is None or reading > best[0]:
                best = (reading, entry)
    return best
