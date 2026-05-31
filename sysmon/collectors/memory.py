"""Memory metrics collector."""

import psutil


def get_memory_info() -> dict:
    """Get current memory usage.

    Returns:
        dict with keys: total, used, available, percent, swap_total, swap_used, swap_percent
    """
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return {
        "total": mem.total,
        "used": mem.used,
        "available": mem.available,
        "percent": mem.percent,
        "swap_total": swap.total,
        "swap_used": swap.used,
        "swap_percent": swap.percent,
    }


def bytes_to_gb(b: float) -> str:
    """Convert bytes to GB string with 1 decimal."""
    return f"{b / (1024 ** 3):.1f}"
