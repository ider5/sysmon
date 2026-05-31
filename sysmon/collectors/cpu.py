"""CPU metrics collector."""

import platform
import re
import subprocess
import threading
import time

import psutil

# Cache for real-time frequency (updated by background thread)
_freq_cache = {'current': 0, 'base': 0, 'timestamp': 0}
_freq_lock = threading.Lock()


def _get_realtime_freq_windows() -> dict:
    """Get real-time CPU frequency on Windows using Performance Counters.

    Returns dict with 'current' and 'base' keys, or empty dict on failure.
    """
    try:
        # Get % Processor Performance counter
        counter = '\\Processor Information(_Total)\\% Processor Performance'
        result = subprocess.run(
            ['typeperf', counter, '-sc', '1'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                match = re.search(r'^"[\d/]+ [\d:.]+","([\d.]+)"$', line)
                if match:
                    perf_percent = float(match.group(1))

                    # Get base frequency (cached by system, fast call)
                    result2 = subprocess.run(
                        ['wmic', 'cpu', 'get', 'MaxClockSpeed', '/value'],
                        capture_output=True, text=True, timeout=3
                    )
                    if result2.returncode == 0:
                        for line2 in result2.stdout.split('\n'):
                            if 'MaxClockSpeed' in line2 and '=' in line2:
                                base_freq = int(line2.split('=')[1].strip())
                                return {
                                    'current': base_freq * perf_percent / 100,
                                    'base': base_freq,
                                }
                    break
    except Exception:
        pass
    return {}


def _freq_collector_thread():
    """Background thread that continuously collects CPU frequency."""
    while True:
        try:
            if platform.system() == 'Windows':
                freq = _get_realtime_freq_windows()
                if freq:
                    with _freq_lock:
                        _freq_cache['current'] = freq['current']
                        _freq_cache['base'] = freq['base']
                        _freq_cache['timestamp'] = time.time()
        except Exception:
            pass
        # Sleep to avoid high CPU usage
        time.sleep(1.5)


def _start_freq_collector():
    """Start the background frequency collector thread (daemon)."""
    t = threading.Thread(target=_freq_collector_thread, daemon=True)
    t.start()


# Start background collector
_start_freq_collector()

# Do initial collection synchronously for immediate data
if platform.system() == 'Windows':
    freq = _get_realtime_freq_windows()
    if freq:
        _freq_cache['current'] = freq['current']
        _freq_cache['base'] = freq['base']
        _freq_cache['timestamp'] = time.time()


def get_cpu_info() -> dict:
    """Get current CPU metrics.

    Returns:
        dict with keys: percent, count_logical, count_physical, freq_current, freq_max
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    count_logical = psutil.cpu_count(logical=True)
    count_physical = psutil.cpu_count(logical=False)

    # Get frequency from cache (updated by background thread)
    freq_current = 0
    freq_max = 0

    if platform.system() == 'Windows':
        with _freq_lock:
            # Use cached value if fresh (< 3 seconds old)
            if _freq_cache['timestamp'] > 0 and (time.time() - _freq_cache['timestamp']) < 3:
                freq_current = _freq_cache['current']
                freq_max = _freq_cache['base']
    else:
        # On Linux/macOS, psutil works better
        freq = psutil.cpu_freq()
        if freq and freq.current:
            freq_current = freq.current
            freq_max = freq.max if freq.max else 0

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
