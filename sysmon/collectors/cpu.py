"""CPU metrics collector."""

import psutil


def get_cpu_info() -> dict:
    """Get current CPU metrics.

    Returns:
        dict with keys: percent, count_logical, count_physical, freq_current, freq_max
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    count_logical = psutil.cpu_count(logical=True)
    count_physical = psutil.cpu_count(logical=False)
    freq = psutil.cpu_freq()

    return {
        "percent": cpu_percent,
        "count_logical": count_logical,
        "count_physical": count_physical,
        "freq_current": freq.current if freq else 0,
        "freq_max": freq.max if freq and freq.max else 0,
    }


def get_per_core_usage() -> list[float]:
    """Get CPU usage per core.

    Returns:
        List of percentages, one per logical core.
    """
    return psutil.cpu_percent(interval=0.1, percpu=True)
