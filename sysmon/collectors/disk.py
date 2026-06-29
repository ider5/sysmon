"""Disk usage and I/O metrics collector."""

from __future__ import annotations

import platform
import threading
import time
from typing import Iterable

import psutil

_prev_disk_io = None
_prev_time: float | None = None
_disk_lock = threading.Lock()


def _primary_mount() -> str:
    """Return the primary disk mount point for the current platform."""
    if platform.system() == "Windows":
        return "C:\\"
    return "/"


def list_mount_points() -> list[str]:
    """Return available disk mount points for the current platform."""
    mounts: list[str] = []
    for part in psutil.disk_partitions(all=False):
        mount = part.mountpoint
        if not mount:
            continue
        if platform.system() != "Windows" and mount.startswith("/dev"):
            continue
        try:
            psutil.disk_usage(mount)
        except (OSError, PermissionError):
            continue
        mounts.append(mount)
    return mounts


def _resolve_mounts(selected: Iterable[str] | None) -> list[str]:
    """Resolve configured mount list; None uses primary mount only."""
    if selected is None:
        return [_primary_mount()]
    mounts = list(selected)
    if not mounts:
        return list_mount_points() or [_primary_mount()]
    return mounts


def _mount_usage(mount: str) -> dict | None:
    try:
        usage = psutil.disk_usage(mount)
    except (OSError, PermissionError):
        return None
    return {
        "mount": mount,
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "percent": usage.percent,
    }


def get_disk_info(mounts: Iterable[str] | None = None) -> dict:
    """Get disk usage and I/O speed.

    Args:
        mounts: Mount points to include. None = primary only; empty = all detected.

    Returns:
        dict with keys: mounts (list), mount/total/used/free/percent (primary compat),
        read_bytes, write_bytes, read_speed, write_speed
    """
    global _prev_disk_io, _prev_time

    resolved = _resolve_mounts(mounts)
    mount_entries: list[dict] = []
    for mount in resolved:
        entry = _mount_usage(mount)
        if entry is not None:
            mount_entries.append(entry)

    if not mount_entries:
        primary = _primary_mount()
        mount_entries = [
            {
                "mount": primary,
                "total": 0,
                "used": 0,
                "free": 0,
                "percent": 0.0,
            }
        ]

    current_io = psutil.disk_io_counters()
    now = time.time()

    read_speed = 0.0
    write_speed = 0.0
    read_bytes = 0
    write_bytes = 0

    if current_io is not None:
        read_bytes = current_io.read_bytes
        write_bytes = current_io.write_bytes

        with _disk_lock:
            if _prev_disk_io is not None and _prev_time is not None:
                dt = now - _prev_time
                if dt > 0:
                    read_speed = (current_io.read_bytes - _prev_disk_io.read_bytes) / dt
                    write_speed = (current_io.write_bytes - _prev_disk_io.write_bytes) / dt

            _prev_disk_io = current_io
            _prev_time = now

    primary = mount_entries[0]
    return {
        "mounts": mount_entries,
        "mount": primary["mount"],
        "total": primary["total"],
        "used": primary["used"],
        "free": primary["free"],
        "percent": primary["percent"],
        "read_bytes": read_bytes,
        "write_bytes": write_bytes,
        "read_speed": read_speed,
        "write_speed": write_speed,
    }
