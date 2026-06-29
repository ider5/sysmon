"""Process metrics collector."""

from __future__ import annotations

import psutil


def get_top_processes(
    limit: int = 10,
    sort_by: str = "cpu",
    name_filter: str | None = None,
) -> list[dict]:
    """Return top processes by CPU or memory usage.

    Args:
        limit: Maximum number of processes to return.
        sort_by: Sort key, either 'cpu' or 'memory'.
        name_filter: Case-insensitive substring filter on process name.

    Returns:
        List of dicts with pid, name, cpu_percent, memory_percent, memory_mb.
    """
    processes: list[dict] = []
    needle = name_filter.lower() if name_filter else None

    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            name = info["name"] or "unknown"
            if needle is not None and needle not in name.lower():
                continue
            mem_info = proc.memory_info()
            processes.append(
                {
                    "pid": info["pid"],
                    "name": name,
                    "cpu_percent": info["cpu_percent"] or 0.0,
                    "memory_percent": info["memory_percent"] or 0.0,
                    "memory_mb": mem_info.rss / (1024 * 1024),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    processes.sort(key=lambda p: p[key], reverse=True)
    return processes[:limit]
