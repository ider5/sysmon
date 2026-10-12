"""Memory metrics collector."""

import math

import psutil


def _zero_memory() -> dict:
    return {
        "total": 0,
        "used": 0,
        "available": 0,
        "percent": 0.0,
        "swap_total": 0,
        "swap_used": 0,
        "swap_percent": 0.0,
    }


def get_memory_info() -> dict:
    """Get current memory usage.

    Returns:
        dict with keys: total, used, available, percent, swap_total, swap_used, swap_percent
    """
    try:
        mem = psutil.virtual_memory()
    except (OSError, RuntimeError, NotImplementedError):
        return _zero_memory()

    try:
        swap = psutil.swap_memory()
    except (OSError, RuntimeError, NotImplementedError):
        swap = None

    return {
        "total": mem.total,
        "used": mem.used,
        "available": mem.available,
        "percent": mem.percent,
        "swap_total": 0 if swap is None else swap.total,
        "swap_used": 0 if swap is None else swap.used,
        "swap_percent": 0.0 if swap is None else swap.percent,
    }


def bytes_to_gb(b: float) -> str:
    """Convert bytes to GB string with 1 decimal."""
    if isinstance(b, bool) or not isinstance(b, (int, float)) or not math.isfinite(b):
        b = 0.0
    return f"{b / (1024 ** 3):.1f}"
