"""Disk usage and I/O metrics collector."""

import platform
import threading
import time

import psutil

_prev_disk_io = None
_prev_time: float | None = None
_disk_lock = threading.Lock()


def _primary_mount() -> str:
    """Return the primary disk mount point for the current platform."""
    if platform.system() == "Windows":
        return "C:\\"
    return "/"


def get_disk_info() -> dict:
    """Get disk usage and I/O speed.

    Returns:
        dict with keys: mount, total, used, free, percent,
        read_bytes, write_bytes, read_speed, write_speed
    """
    global _prev_disk_io, _prev_time

    mount = _primary_mount()
    usage = psutil.disk_usage(mount)
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

    return {
        "mount": mount,
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "percent": usage.percent,
        "read_bytes": read_bytes,
        "write_bytes": write_bytes,
        "read_speed": read_speed,
        "write_speed": write_speed,
    }
