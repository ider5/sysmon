"""Network metrics collector."""

from __future__ import annotations

import math
import threading
import time
from typing import Iterable

import psutil

_prev_net_io = None
_prev_time: float | None = None
_prev_iface_io: dict[str, object] = {}
_prev_iface_time: float | None = None
_net_lock = threading.Lock()


def _interface_link() -> dict[str, dict[str, int | bool]]:
    """Return link speed in Mb/s and duplex-up flag for each interface."""
    try:
        stats = psutil.net_if_stats()
    except (OSError, RuntimeError, NotImplementedError, AttributeError):
        return {}
    links: dict[str, dict[str, int | bool]] = {}
    for name, info in stats.items():
        link: dict[str, int | bool] = {"isup": bool(getattr(info, "isup", False))}
        speed = getattr(info, "speed", 0) or 0
        if (
            not isinstance(speed, bool)
            and isinstance(speed, (int, float))
            and math.isfinite(speed)
            and 0 < speed <= 1_000_000_000
        ):
            link["speed_mbps"] = int(speed)
        links[name] = link
    return links


def _link_fields(name: str, links: dict[str, dict[str, int | bool]]) -> dict[str, int | bool]:
    """Copy link speed and up/down state onto one interface record."""
    link = links.get(name)
    if not isinstance(link, dict):
        return {}
    fields: dict[str, int | bool] = {}
    if "speed_mbps" in link:
        fields["speed_mbps"] = link["speed_mbps"]
    if "isup" in link:
        fields["isup"] = bool(link["isup"])
    return fields


def _error_counts(obj: object) -> dict[str, int]:
    """Read NIC error and drop counters, using zero when a field is absent."""
    counts: dict[str, int] = {}
    for name in ("errin", "errout", "dropin", "dropout"):
        value = getattr(obj, name, 0) if obj is not None else 0
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            value = 0
        counts[name] = int(value)
    return counts


def _finite_counter(value: object) -> float:
    """Return a finite counter, or zero when the sample is unusable."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return 0.0
    return float(value)


def _prev_bytes(prev: object) -> tuple[float, float]:
    if isinstance(prev, tuple):
        return float(prev[0]), float(prev[1])
    return (
        _finite_counter(getattr(prev, "bytes_sent", 0)),
        _finite_counter(getattr(prev, "bytes_recv", 0)),
    )


def _delta_rate(current: float, previous: float, dt: float) -> float:
    if dt <= 0:
        return 0.0
    delta = current - previous
    return delta / dt if delta >= 0 else 0.0


def list_network_interfaces() -> list[str]:
    """Return non-loopback network interface names."""
    try:
        stats = psutil.net_if_stats()
    except (OSError, RuntimeError, NotImplementedError, AttributeError):
        return []
    if not isinstance(stats, dict):
        return []
    names: list[str] = []
    for name, info in stats.items():
        if not isinstance(name, str) or name.lower().startswith("lo"):
            continue
        if not bool(getattr(info, "isup", False)):
            continue
        names.append(name)
    return sorted(names)


def _resolve_interfaces(selected: Iterable[str] | None) -> list[str] | None:
    """Resolve interface filter; None = aggregate all, empty = all non-loopback."""
    if selected is None:
        return None
    names: list[str] = []
    seen: set[str] = set()
    for item in selected:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        names.append(text)
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
    now = time.time()

    if resolved is not None:
        try:
            per_nic = psutil.net_io_counters(pernic=True) or {}
        except (OSError, RuntimeError):
            per_nic = {}
        links = _interface_link()
        iface_entries: list[dict] = []
        with _net_lock:
            for name in resolved:
                counters = per_nic.get(name)
                if counters is None:
                    _prev_iface_io.pop(name, None)
                    iface_entries.append(
                        {
                            "name": name,
                            "bytes_sent": 0,
                            "bytes_recv": 0,
                            "speed_up": 0.0,
                            "speed_down": 0.0,
                            "packets_sent": 0,
                            "packets_recv": 0,
                            **_error_counts(None),
                            **_link_fields(name, links),
                        }
                    )
                    continue
                sent = _finite_counter(getattr(counters, "bytes_sent", 0))
                recv = _finite_counter(getattr(counters, "bytes_recv", 0))
                prev = _prev_iface_io.get(name)
                if prev is not None and _prev_iface_time is not None:
                    dt = now - _prev_iface_time
                    prev_sent, prev_recv = _prev_bytes(prev)
                    speed_up = _delta_rate(sent, prev_sent, dt)
                    speed_down = _delta_rate(recv, prev_recv, dt)
                else:
                    speed_up = 0.0
                    speed_down = 0.0
                iface_entries.append(
                    {
                        "name": name,
                        "bytes_sent": sent,
                        "bytes_recv": recv,
                        "speed_up": speed_up,
                        "speed_down": speed_down,
                        "packets_sent": _finite_counter(getattr(counters, "packets_sent", 0)),
                        "packets_recv": _finite_counter(getattr(counters, "packets_recv", 0)),
                        **_error_counts(counters),
                        **_link_fields(name, links),
                    }
                )
                _prev_iface_io[name] = (sent, recv)
            _prev_iface_time = now

        result = {
            "bytes_sent": sum(item["bytes_sent"] for item in iface_entries),
            "bytes_recv": sum(item["bytes_recv"] for item in iface_entries),
            "speed_up": sum(item["speed_up"] for item in iface_entries),
            "speed_down": sum(item["speed_down"] for item in iface_entries),
            "packets_sent": sum(item["packets_sent"] for item in iface_entries),
            "packets_recv": sum(item["packets_recv"] for item in iface_entries),
            "errin": sum(item["errin"] for item in iface_entries),
            "errout": sum(item["errout"] for item in iface_entries),
            "dropin": sum(item["dropin"] for item in iface_entries),
            "dropout": sum(item["dropout"] for item in iface_entries),
        }
        if iface_entries:
            result["interfaces"] = iface_entries
        return result

    try:
        current = psutil.net_io_counters()
    except (OSError, RuntimeError):
        current = None
    if current is None:
        return {
            "bytes_sent": 0,
            "bytes_recv": 0,
            "speed_up": 0.0,
            "speed_down": 0.0,
            "packets_sent": 0,
            "packets_recv": 0,
            **_error_counts(None),
        }

    sent = _finite_counter(getattr(current, "bytes_sent", 0))
    recv = _finite_counter(getattr(current, "bytes_recv", 0))
    with _net_lock:
        if _prev_net_io is not None and _prev_time is not None:
            dt = now - _prev_time
            prev_sent, prev_recv = _prev_bytes(_prev_net_io)
            speed_up = _delta_rate(sent, prev_sent, dt)
            speed_down = _delta_rate(recv, prev_recv, dt)
        else:
            speed_up = 0.0
            speed_down = 0.0

        _prev_net_io = (sent, recv)
        _prev_time = now

    return {
        "bytes_sent": sent,
        "bytes_recv": recv,
        "speed_up": speed_up,
        "speed_down": speed_down,
        "packets_sent": _finite_counter(getattr(current, "packets_sent", 0)),
        "packets_recv": _finite_counter(getattr(current, "packets_recv", 0)),
        **_error_counts(current),
    }


def down_interface_names(info: object) -> list[str]:
    """Return names of interfaces whose link is explicitly down."""
    if not isinstance(info, dict):
        return []
    interfaces = info.get("interfaces")
    if not isinstance(interfaces, list):
        return []
    names: list[str] = []
    for iface in interfaces:
        if not isinstance(iface, dict) or iface.get("isup") is not False:
            continue
        text = " ".join(str(iface.get("name") or "unknown").split()) or "unknown"
        names.append(text)
    return names


def format_bytes(b: float) -> str:
    """Format bytes to human-readable string."""
    if isinstance(b, bool) or not isinstance(b, (int, float)) or not math.isfinite(b):
        b = 0.0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def format_speed(bps: float) -> str:
    """Format bytes per second to human-readable string."""
    return f"{format_bytes(bps)}/s"
