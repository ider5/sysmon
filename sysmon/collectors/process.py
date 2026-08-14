"""Process metrics collector."""

from __future__ import annotations

import threading
import time

import psutil

_prev_cpu: dict[tuple[int, float], tuple[float, float]] = {}
_cpu_lock = threading.Lock()


def clear_process_cpu_cache() -> None:
    """Drop cached CPU times (used by tests)."""
    with _cpu_lock:
        _prev_cpu.clear()


def _proc_key(proc: psutil.Process) -> tuple[int, float]:
    return (proc.pid, float(proc.create_time()))


def _cpu_percent(proc: psutil.Process) -> float:
    """Return CPU percent from a pid-level sample cache."""
    times = proc.cpu_times()
    proc_time = float(times.user + times.system)
    now = time.monotonic()
    key = _proc_key(proc)
    with _cpu_lock:
        prev = _prev_cpu.get(key)
        _prev_cpu[key] = (proc_time, now)
    if prev is None:
        return 0.0
    prev_proc, prev_wall = prev
    dt = now - prev_wall
    if dt <= 0:
        return 0.0
    return max(0.0, (proc_time - prev_proc) / dt * 100.0)


def _prime_cpu_times() -> None:
    for proc in psutil.process_iter():
        try:
            _cpu_percent(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue


def _evict_stale_cpu_cache(alive: set[tuple[int, float]]) -> None:
    with _cpu_lock:
        stale = [key for key in _prev_cpu if key not in alive]
        for key in stale:
            del _prev_cpu[key]


def get_top_processes(
    limit: int = 10,
    sort_by: str = "cpu",
    name_filter: str | None = None,
    sample_interval: float | None = None,
) -> list[dict]:
    """Return top processes by CPU or memory usage.

    Args:
        limit: Maximum number of processes to return.
        sort_by: Sort key, either 'cpu' or 'memory'.
        name_filter: Case-insensitive substring filter on process name.
        sample_interval: If set, prime CPU times then sleep before sampling
            so one-shot calls return non-zero cpu_percent values.

    Returns:
        List of dicts with pid, name, cpu_percent, memory_percent, memory_mb.
    """
    if sample_interval is not None and sample_interval > 0:
        _prime_cpu_times()
        time.sleep(sample_interval)

    processes: list[dict] = []
    needle = name_filter.lower() if name_filter else None
    alive: set[tuple[int, float]] = set()

    for proc in psutil.process_iter(["pid", "name", "memory_percent"]):
        try:
            alive.add(_proc_key(proc))
            info = proc.info
            name = info["name"] or "unknown"
            if needle is not None and needle not in name.lower():
                continue
            mem_info = proc.memory_info()
            processes.append(
                {
                    "pid": info["pid"],
                    "name": name,
                    "cpu_percent": _cpu_percent(proc),
                    "memory_percent": info["memory_percent"] or 0.0,
                    "memory_mb": mem_info.rss / (1024 * 1024),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    _evict_stale_cpu_cache(alive)

    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    processes.sort(key=lambda p: p[key], reverse=True)
    return processes[:limit]
