"""CPU metrics collector."""

import platform
import re
import subprocess

import psutil


def _get_realtime_freq_windows() -> dict:
    """Get real-time CPU frequency on Windows using Performance Counters.

    Returns dict with 'current' and 'base' keys, or empty dict on failure.
    """
    try:
        # Get % Processor Performance counter
        # Note: typeperf expects \\server\counter format
        counter = '\\Processor Information(_Total)\\% Processor Performance'
        result = subprocess.run(
            ['typeperf', counter, '-sc', '1'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            # Find the data line (format: "timestamp","value")
            for line in result.stdout.split('\n'):
                match = re.search(r'^"[\d/]+ [\d:.]+","([\d.]+)"$', line)
                if match:
                    perf_percent = float(match.group(1))

                    # Get base frequency
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


def get_cpu_info() -> dict:
    """Get current CPU metrics.

    Returns:
        dict with keys: percent, count_logical, count_physical, freq_current, freq_max
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    count_logical = psutil.cpu_count(logical=True)
    count_physical = psutil.cpu_count(logical=False)

    # Try to get real-time frequency
    freq_current = 0
    freq_max = 0

    if platform.system() == 'Windows':
        freq = _get_realtime_freq_windows()
        if freq:
            freq_current = freq['current']
            freq_max = freq['base']
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
