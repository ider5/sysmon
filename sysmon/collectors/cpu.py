"""CPU metrics collector."""

from __future__ import annotations

import math
import platform
import re
import subprocess
import threading
import time

import psutil

# Cache for real-time frequency (updated by background thread)
_freq_cache = {"current": 0, "base": 0, "timestamp": 0}
_freq_lock = threading.Lock()
_collector_started = False
_collector_lock = threading.Lock()


def _get_base_freq_windows() -> int:
    """Get CPU base/max clock speed on Windows via PowerShell CIM."""
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor | Select-Object -First 1).MaxClockSpeed",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            value = result.stdout.strip()
            if value.isdigit():
                return int(value)
    except Exception:
        pass

    freq = _psutil_cpu_freq()
    if freq and freq.max:
        return int(freq.max)
    return 0


def _get_realtime_freq_windows() -> dict:
    """Get real-time CPU frequency on Windows using Performance Counters.

    Returns dict with 'current' and 'base' keys, or empty dict on failure.
    """
    try:
        counter = r"\Processor Information(_Total)\% Processor Performance"
        result = subprocess.run(
            ["typeperf", counter, "-sc", "1"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                match = re.search(r'^"[\d/]+ [\d:.]+","([\d.]+)"$', line)
                if match:
                    perf_percent = float(match.group(1))
                    base_freq = _get_base_freq_windows()
                    if base_freq:
                        return {
                            "current": base_freq * perf_percent / 100,
                            "base": base_freq,
                        }
                    break
    except Exception:
        pass
    return {}


def _freq_collector_thread() -> None:
    """Background thread that continuously collects CPU frequency."""
    while True:
        try:
            if platform.system() == "Windows":
                freq = _get_realtime_freq_windows()
                if freq:
                    with _freq_lock:
                        _freq_cache["current"] = freq["current"]
                        _freq_cache["base"] = freq["base"]
                        _freq_cache["timestamp"] = time.time()
        except Exception:
            pass
        time.sleep(1.5)


def _psutil_cpu_freq():
    """Return psutil.cpu_freq() or None when the platform does not expose it."""
    cpu_freq = getattr(psutil, "cpu_freq", None)
    if cpu_freq is None:
        return None
    try:
        return cpu_freq()
    except (AttributeError, NotImplementedError, OSError, RuntimeError):
        return None


def _ensure_freq_collector() -> None:
    """Start the background frequency collector on first use."""
    if platform.system() != "Windows":
        return
    global _collector_started
    with _collector_lock:
        if _collector_started:
            return
        _collector_started = True
        thread = threading.Thread(target=_freq_collector_thread, daemon=True)
        thread.start()
        freq = _get_realtime_freq_windows()
        if freq:
            with _freq_lock:
                _freq_cache["current"] = freq["current"]
                _freq_cache["base"] = freq["base"]
                _freq_cache["timestamp"] = time.time()


def _freq_mhz(value: object) -> float:
    """Return a non-negative finite frequency in MHz, or zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return 0.0
    if value < 0:
        return 0.0
    return float(value)


def _get_freq_fields() -> tuple[float, float]:
    """Return current and max CPU frequency in MHz."""
    freq_current = 0.0
    freq_max = 0.0

    if platform.system() == "Windows":
        with _freq_lock:
            if _freq_cache["timestamp"] > 0 and (time.time() - _freq_cache["timestamp"]) < 3:
                freq_current = _freq_mhz(_freq_cache["current"])
                freq_max = _freq_mhz(_freq_cache["base"])
    else:
        freq = _psutil_cpu_freq()
        if freq and freq.current:
            freq_current = _freq_mhz(freq.current)
            freq_max = _freq_mhz(freq.max)

    return freq_current, freq_max


def _load_average() -> tuple[float, float, float] | None:
    """Return 1, 5, and 15 minute load averages when the OS provides them."""
    getloadavg = getattr(psutil, "getloadavg", None)
    if getloadavg is None:
        return None
    try:
        one, five, fifteen = getloadavg()
        values = (float(one), float(five), float(fifteen))
    except (OSError, RuntimeError, NotImplementedError, AttributeError, TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in values):
        return None
    return values


def get_cpu_snapshot(interval: float = 0.1) -> dict:
    """Get CPU metrics in a single sampling pass.

    Returns:
        dict with keys: percent, cores, count_logical, count_physical,
        freq_current, freq_max
    """
    _ensure_freq_collector()
    try:
        raw_cores = psutil.cpu_percent(interval=interval, percpu=True) or []
    except (OSError, RuntimeError, NotImplementedError):
        raw_cores = []
    if not isinstance(raw_cores, list):
        raw_cores = []
    cores = [
        float(core)
        for core in raw_cores
        if isinstance(core, (int, float))
        and not isinstance(core, bool)
        and math.isfinite(core)
    ]
    overall = sum(cores) / len(cores) if cores else 0.0
    freq_current, freq_max = _get_freq_fields()
    logical = psutil.cpu_count(logical=True) or 0
    physical = psutil.cpu_count(logical=False) or logical

    return {
        "percent": overall,
        "cores": cores,
        "count_logical": logical,
        "count_physical": physical,
        "freq_current": freq_current,
        "freq_max": freq_max,
        "load_avg": _load_average(),
    }


def get_cpu_info() -> dict:
    """Get current CPU metrics.

    Returns:
        dict with keys: percent, count_logical, count_physical, freq_current, freq_max
    """
    snapshot = get_cpu_snapshot()
    return {
        "percent": snapshot["percent"],
        "count_logical": snapshot["count_logical"],
        "count_physical": snapshot["count_physical"],
        "freq_current": snapshot["freq_current"],
        "freq_max": snapshot["freq_max"],
    }


def get_per_core_usage() -> list[float]:
    """Get CPU usage per core.

    Returns:
        List of percentages, one per logical core.
    """
    return get_cpu_snapshot()["cores"]
