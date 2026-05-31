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

    # On Windows, psutil.cpu_freq() often returns base frequency (current == max)
    # which is not the real-time frequency. Only report if we get dynamic values.
    freq_current = 0
    freq_max = 0
    if freq and freq.current and freq.max and freq.current != freq.max:
        freq_current = freq.current
        freq_max = freq.max

    return {
        "percent": cpu_percent,
        "count_logical": count_logical,
        "count_physical": count_physical,
        "freq_current": freq_current,
        "freq_max": freq_max,
    }


def get_per_core_usage() -> list[float]:
    """Get CPU usage per core.

    Returns:
        List of percentages, one per logical core.
    """
    return psutil.cpu_percent(interval=0.1, percpu=True)
