"""Battery and temperature sensors (opt-in)."""

from __future__ import annotations

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
        secsleft = getattr(reading, "secsleft", None)
        unlimited = getattr(psutil, "POWER_TIME_UNLIMITED", -1)
        unknown = getattr(psutil, "POWER_TIME_UNKNOWN", -2)
        if secsleft in (None, unlimited, unknown) or (
            isinstance(secsleft, (int, float)) and secsleft < 0
        ):
            remaining = None
        else:
            remaining = int(secsleft)
        battery = {
            "percent": float(reading.percent),
            "secsleft": remaining,
            "power_plugged": bool(reading.power_plugged),
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
    for name, entries in grouped.items():
        temperatures[name] = [
            {
                "label": entry.label or "",
                "current": None if entry.current is None else float(entry.current),
                "high": getattr(entry, "high", None),
                "critical": getattr(entry, "critical", None),
            }
            for entry in entries
        ]
    return {"battery": battery, "temperatures": temperatures}
