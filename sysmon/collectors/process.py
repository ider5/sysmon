"""Process metrics collector."""

from __future__ import annotations

import heapq
import threading
import time

import psutil

_prev_cpu: dict[tuple[int, float], tuple[float, float]] = {}
_cpu_lock = threading.Lock()

PROCESS_ITER_ATTRS = (
    "pid",
    "name",
    "cpu_times",
    "memory_info",
    "create_time",
    "memory_percent",
)


def clear_process_cpu_cache() -> None:
    """Drop cached CPU times (used by tests)."""
    with _cpu_lock:
        _prev_cpu.clear()


def _create_time(proc: psutil.Process, info: dict) -> float:
    value = info.get("create_time")
    if value is not None:
        return float(value)
    return float(proc.create_time())


def _proc_key(proc: psutil.Process, info: dict | None = None) -> tuple[int, float]:
    payload = info if info is not None else getattr(proc, "info", {}) or {}
    pid = payload.get("pid", proc.pid)
    return (int(pid), _create_time(proc, payload))


def _cpu_percent_from_times(key: tuple[int, float], times) -> float:
    proc_time = float(times.user + times.system)
    now = time.monotonic()
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


def _cpu_times(proc: psutil.Process, info: dict):
    value = info.get("cpu_times")
    if value is not None:
        return value
    return proc.cpu_times()


def _memory_info(proc: psutil.Process, info: dict):
    value = info.get("memory_info")
    if value is not None:
        return value
    return proc.memory_info()


def _cpu_percent(proc: psutil.Process) -> float:
    """Return CPU percent from a pid-level sample cache."""
    info = getattr(proc, "info", {}) or {}
    return _cpu_percent_from_times(_proc_key(proc, info), _cpu_times(proc, info))


def _prime_cpu_times() -> None:
    for proc in psutil.process_iter(list(PROCESS_ITER_ATTRS)):
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
    native = _try_native_processes(limit, sort_by, name_filter, sample_interval)
    if native is not None:
        return native

    if sample_interval is not None and sample_interval > 0:
        _prime_cpu_times()
        time.sleep(sample_interval)

    processes: list[dict] = []
    needle = name_filter.lower() if name_filter else None
    alive: set[tuple[int, float]] = set()

    for proc in psutil.process_iter(list(PROCESS_ITER_ATTRS)):
        try:
            info = getattr(proc, "info", {}) or {}
            key = _proc_key(proc, info)
            alive.add(key)
            name = info.get("name") or "unknown"
            if needle is not None and needle not in name.lower():
                continue
            mem_info = _memory_info(proc, info)
            processes.append(
                {
                    "pid": info.get("pid", proc.pid),
                    "name": name,
                    "cpu_percent": _cpu_percent_from_times(key, _cpu_times(proc, info)),
                    "memory_percent": info.get("memory_percent") or 0.0,
                    "memory_mb": mem_info.rss / (1024 * 1024),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    _evict_stale_cpu_cache(alive)

    sort_key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    if limit <= 0:
        return []
    return heapq.nlargest(limit, processes, key=lambda item: item[sort_key])


def _try_native_processes(
    limit: int,
    sort_by: str,
    name_filter: str | None,
    sample_interval: float | None,
) -> list[dict] | None:
    """Use the optional Rust backend when no one-shot sample sleep is required."""
    if sample_interval is not None and sample_interval > 0:
        return None
    try:
        from sysmon._core import list_processes
    except ImportError:
        return None
    try:
        return list_processes(limit, sort_by, name_filter)
    except Exception:
        return None
