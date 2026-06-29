"""Network metrics collector."""

from __future__ import annotations

import threading
import time
from typing import Iterable

import psutil

_prev_net_io = None
_prev_time: float | None = None
_prev_iface_io: dict[str, object] = {}
_prev_iface_time: float | None = None
_net_lock = threading.Lock()


def list_network_interfaces() -> list[str]:
    """Return non-loopback network interface names."""
    stats = psutil.net_if_stats()
    return sorted(
        name
        for name, info in stats.items()
        if info.isup and not name.lower().startswith("lo")
    )


def _resolve_interfaces(selected: Iterable[str] | None) -> list[str] | None:
    """Resolve interface filter; None = aggregate all, empty = all non-loopback."""
    if selected is None:
        return None
    names = list(selected)
    if not names:
        return list_network_interfaces()
    return names


def get_network_info(interfaces: Iterable[str] | None = None) -> dict:
    """Get current network I/O with speed calculation.

    Args:
        interfaces: Interface names to include. None = aggregate totals only;
            empty list = all non-loopback interfaces with per-interface stats.

    Returns:
        dict with aggregate counters/speeds and optional interfaces list.
    """
    global _prev_net_io, _prev_time, _prev_iface_io, _prev_iface_time

    resolved = _resolve_interfaces(interfaces)
    per_nic = psutil.net_io_counters(pernic=True)
    now = time.time()

    iface_entries: list[dict] = []
    if resolved is not None:
        with _net_lock:
            for name in resolved:
                counters = per_nic.get(name)
                if counters is None:
                    continue
                prev = _prev_iface_io.get(name)
                if prev is not None and _prev_iface_time is not None:
                    dt = now - _prev_iface_time
                    if dt > 0:
                        speed_up = (counters.bytes_sent - prev.bytes_sent) / dt
                        speed_down = (counters.bytes_recv - prev.bytes_recv) / dt
                    else:
                        speed_up = 0.0
                        speed_down = 0.0
                else:
                    speed_up = 0.0
                    speed_down = 0.0
                iface_entries.append(
                    {
                        "name": name,
                        "bytes_sent": counters.bytes_sent,
                        "bytes_recv": counters.bytes_recv,
                        "speed_up": speed_up,
                        "speed_down": speed_down,
                        "packets_sent": counters.packets_sent,
                        "packets_recv": counters.packets_recv,
                    }
                )
                _prev_iface_io[name] = counters
            _prev_iface_time = now

    current = psutil.net_io_counters()
    with _net_lock:
        if _prev_net_io is not None and _prev_time is not None:
            dt = now - _prev_time
            if dt > 0:
                speed_up = (current.bytes_sent - _prev_net_io.bytes_sent) / dt
                speed_down = (current.bytes_recv - _prev_net_io.bytes_recv) / dt
            else:
                speed_up = 0
                speed_down = 0
        else:
            speed_up = 0
            speed_down = 0

        _prev_net_io = current
        _prev_time = now

    result = {
        "bytes_sent": current.bytes_sent,
        "bytes_recv": current.bytes_recv,
        "speed_up": speed_up,
        "speed_down": speed_down,
        "packets_sent": current.packets_sent,
        "packets_recv": current.packets_recv,
    }
    if iface_entries:
        result["interfaces"] = iface_entries
    return result


def format_bytes(b: float) -> str:
    """Format bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def format_speed(bps: float) -> str:
    """Format bytes per second to human-readable string."""
    return f"{format_bytes(bps)}/s"
