"""CPU metrics collector."""

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

    freq = psutil.cpu_freq()
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


def _ensure_freq_collector() -> None:
    """Start the background frequency collector on first use."""
    global _collector_started
    with _collector_lock:
        if _collector_started:
            return
        _collector_started = True
        thread = threading.Thread(target=_freq_collector_thread, daemon=True)
        thread.start()
        if platform.system() == "Windows":
            freq = _get_realtime_freq_windows()
            if freq:
                with _freq_lock:
                    _freq_cache["current"] = freq["current"]
                    _freq_cache["base"] = freq["base"]
                    _freq_cache["timestamp"] = time.time()


def _get_freq_fields() -> tuple[float, float]:
    """Return current and max CPU frequency in MHz."""
    freq_current = 0.0
    freq_max = 0.0

    if platform.system() == "Windows":
        with _freq_lock:
            if _freq_cache["timestamp"] > 0 and (time.time() - _freq_cache["timestamp"]) < 3:
                freq_current = _freq_cache["current"]
                freq_max = _freq_cache["base"]
    else:
        freq = psutil.cpu_freq()
        if freq and freq.current:
            freq_current = freq.current
            freq_max = freq.max if freq.max else 0

    return freq_current, freq_max


def get_cpu_snapshot(interval: float = 0.1) -> dict:
    """Get CPU metrics in a single sampling pass.

    Returns:
        dict with keys: percent, cores, count_logical, count_physical,
        freq_current, freq_max
    """
    _ensure_freq_collector()
    cores = psutil.cpu_percent(interval=interval, percpu=True)
    overall = sum(cores) / len(cores) if cores else 0.0
    freq_current, freq_max = _get_freq_fields()

    return {
        "percent": overall,
        "cores": cores,
        "count_logical": psutil.cpu_count(logical=True),
        "count_physical": psutil.cpu_count(logical=False),
        "freq_current": freq_current,
        "freq_max": freq_max,
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
