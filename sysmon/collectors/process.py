"""Process metrics collector."""

import psutil


def get_top_processes(limit: int = 10, sort_by: str = "cpu") -> list[dict]:
    """Return top processes by CPU or memory usage.

    Args:
        limit: Maximum number of processes to return.
        sort_by: Sort key, either 'cpu' or 'memory'.

    Returns:
        List of dicts with pid, name, cpu_percent, memory_percent, memory_mb.
    """
    processes: list[dict] = []

    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            mem_info = proc.memory_info()
            processes.append(
                {
                    "pid": info["pid"],
                    "name": info["name"] or "unknown",
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
