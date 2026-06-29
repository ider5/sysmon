"""Network metrics collector."""

import threading
import time

import psutil

_prev_net_io = None
_prev_time: float | None = None
_net_lock = threading.Lock()


def get_network_info() -> dict:
    """Get current network I/O with speed calculation.

    Returns:
        dict with keys: bytes_sent, bytes_recv, speed_up, speed_down,
                        packets_sent, packets_recv
    """
    global _prev_net_io, _prev_time

    current = psutil.net_io_counters()
    now = time.time()

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

    return {
        "bytes_sent": current.bytes_sent,
        "bytes_recv": current.bytes_recv,
        "speed_up": speed_up,
        "speed_down": speed_down,
        "packets_sent": current.packets_sent,
        "packets_recv": current.packets_recv,
    }


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
