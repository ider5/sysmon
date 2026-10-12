"""Disk usage and I/O metrics collector."""

from __future__ import annotations

import math
import os
import platform
import threading
import time
from typing import Iterable

import psutil

_prev_disk_io = None
_prev_time: float | None = None
_disk_lock = threading.Lock()
_SKIP_FSTYPES = frozenset(
    {
        "autofs",
        "binfmt_misc",
        "bpf",
        "cgroup",
        "cgroup2",
        "configfs",
        "debugfs",
        "devtmpfs",
        "efivarfs",
        "fusectl",
        "hugetlbfs",
        "mqueue",
        "nsfs",
        "overlay",
        "proc",
        "pstore",
        "ramfs",
        "securityfs",
        "squashfs",
        "sysfs",
        "tmpfs",
        "tracefs",
    }
)


def _counter(value: object) -> float:
    """Return a finite byte counter, or zero when the sample is unusable."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return 0.0
    return float(value)


def _delta_rate(current: float, previous: float, dt: float) -> float:
    if dt <= 0:
        return 0.0
    delta = current - previous
    return delta / dt if delta >= 0 else 0.0


def _primary_mount() -> str:
    """Return the primary disk mount point for the current platform."""
    if platform.system() == "Windows":
        return "C:\\"
    return "/"


def list_mount_points() -> list[str]:
    """Return available disk mount points for the current platform."""
    try:
        parts = psutil.disk_partitions(all=False)
    except (OSError, RuntimeError, NotImplementedError):
        return []
    if not isinstance(parts, list):
        return []
    mounts: list[str] = []
    for part in parts:
        mount = getattr(part, "mountpoint", "") or ""
        if not isinstance(mount, str) or not mount:
            continue
        if (getattr(part, "fstype", "") or "").lower() in _SKIP_FSTYPES:
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
    mounts = [item.strip() for item in selected if isinstance(item, str) and item.strip()]
    if not mounts:
        return list_mount_points() or [_primary_mount()]
    return mounts


def _mount_key(mount: str) -> str:
    """Normalize a mount path so trailing slashes still match."""
    normalized = os.path.normpath(mount)
    if platform.system() == "Windows":
        return normalized.replace("/", "\\").lower()
    return normalized


def _filesystem_types() -> dict[str, str]:
    """Map mount points to filesystem types. Empty when the OS call fails."""
    try:
        parts = psutil.disk_partitions(all=True)
    except (OSError, RuntimeError, NotImplementedError):
        return {}
    types: dict[str, str] = {}
    for part in parts:
        mount = getattr(part, "mountpoint", "") or ""
        fstype = getattr(part, "fstype", "") or ""
        if isinstance(mount, str) and mount and isinstance(fstype, str) and fstype:
            types[_mount_key(mount)] = fstype
    return types


def _inode_percent(mount: str) -> float | None:
    """Return inode usage percent on platforms that expose statvfs."""
    statvfs = getattr(os, "statvfs", None)
    if statvfs is None:
        return None
    try:
        stats = statvfs(mount)
    except OSError:
        return None
    files = getattr(stats, "f_files", 0) or 0
    free = getattr(stats, "f_ffree", 0) or 0
    if (
        isinstance(files, bool)
        or isinstance(free, bool)
        or not isinstance(files, (int, float))
        or not isinstance(free, (int, float))
        or not math.isfinite(files)
        or not math.isfinite(free)
        or files <= 0
    ):
        return None
    percent = (files - free) / files * 100.0
    if not math.isfinite(percent):
        return None
    return max(0.0, min(100.0, float(percent)))


def _mount_usage(mount: str) -> dict | None:
    try:
        usage = psutil.disk_usage(mount)
    except (OSError, PermissionError):
        return None
    entry = {
        "mount": mount,
        "total": _counter(getattr(usage, "total", 0)),
        "used": _counter(getattr(usage, "used", 0)),
        "free": _counter(getattr(usage, "free", 0)),
        "percent": _counter(getattr(usage, "percent", 0)),
    }
    inode_percent = _inode_percent(mount)
    if inode_percent is not None:
        entry["inode_percent"] = inode_percent
    return entry


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
    fstypes = _filesystem_types()
    mount_entries: list[dict] = []
    for mount in resolved:
        entry = _mount_usage(mount)
        if entry is None:
            entry = {
                "mount": mount,
                "total": 0,
                "used": 0,
                "free": 0,
                "percent": 0.0,
            }
        fstype = fstypes.get(_mount_key(mount))
        if fstype:
            entry["fstype"] = fstype
        mount_entries.append(entry)

    if not mount_entries:
        mount_entries = [
            {
                "mount": _primary_mount(),
                "total": 0,
                "used": 0,
                "free": 0,
                "percent": 0.0,
            }
        ]

    try:
        current_io = psutil.disk_io_counters()
    except (OSError, RuntimeError):
        current_io = None
    now = time.time()

    read_speed = 0.0
    write_speed = 0.0
    read_bytes = 0
    write_bytes = 0

    if current_io is not None:
        read_bytes = _counter(getattr(current_io, "read_bytes", 0))
        write_bytes = _counter(getattr(current_io, "write_bytes", 0))

        with _disk_lock:
            if _prev_disk_io is not None and _prev_time is not None:
                dt = now - _prev_time
                if isinstance(_prev_disk_io, tuple):
                    prev_read, prev_write = _prev_disk_io
                else:
                    prev_read = _counter(getattr(_prev_disk_io, "read_bytes", 0))
                    prev_write = _counter(getattr(_prev_disk_io, "write_bytes", 0))
                read_speed = _delta_rate(read_bytes, prev_read, dt)
                write_speed = _delta_rate(write_bytes, prev_write, dt)

            _prev_disk_io = (read_bytes, write_bytes)
            _prev_time = now

    primary = mount_entries[0]
    result = {
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
    if "inode_percent" in primary:
        result["inode_percent"] = primary["inode_percent"]
    return result
