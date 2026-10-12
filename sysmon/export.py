"""Structured data export for sysmon."""

from __future__ import annotations

import json
import platform
import time
from typing import Any, Optional

from sysmon import __version__
from sysmon.collectors.registry import collect
from sysmon.config import SysmonConfig, load_config, metric_status
from sysmon.display.components import _get_os_name, _get_uptime

SCHEMA_VERSION = 3
_MISSING = object()


def _resolve_settings(settings: SysmonConfig | None) -> SysmonConfig:
    return settings if settings is not None else load_config()


def _cpu_payload(
    settings: SysmonConfig | None = None,
    info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _resolve_settings(settings)
    snapshot = info if info is not None else collect("cpu", cfg)

    def _number(key: str, default: float = 0.0) -> float:
        value = snapshot.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default
        return float(value)

    percent = _number("percent")
    status = metric_status(percent, cfg.thresholds.cpu_warn, cfg.thresholds.cpu_critical)
    cores = snapshot.get("cores")
    payload = {
        "percent": percent,
        "cores": cores if isinstance(cores, list) else [],
        "count_logical": int(_number("count_logical")),
        "count_physical": int(_number("count_physical")),
        "freq_current_mhz": _number("freq_current"),
        "freq_max_mhz": _number("freq_max"),
        "status": status,
    }
    load_avg = snapshot.get("load_avg")
    if (
        isinstance(load_avg, (list, tuple))
        and len(load_avg) == 3
        and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in load_avg)
    ):
        payload["load_avg"] = [float(item) for item in load_avg]
    return payload


def _memory_payload(
    settings: SysmonConfig | None = None,
    info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _resolve_settings(settings)
    info = info if info is not None else collect("memory", cfg)

    def _number(key: str, default: float = 0.0) -> float:
        value = info.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default
        return float(value)

    percent = _number("percent")
    return {
        "total": int(_number("total")),
        "used": int(_number("used")),
        "available": int(_number("available")),
        "percent": percent,
        "swap_total": int(_number("swap_total")),
        "swap_used": int(_number("swap_used")),
        "swap_percent": _number("swap_percent"),
        "status": metric_status(
            percent,
            cfg.thresholds.memory_warn,
            cfg.thresholds.memory_critical,
        ),
    }


def _network_payload(
    settings: SysmonConfig | None = None,
    info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _resolve_settings(settings)
    info = info if info is not None else collect("network", cfg)

    def _count(key: str) -> int:
        value = info.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 0
        return int(value)

    def _rate(key: str) -> float:
        value = info.get(key, 0.0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 0.0
        return float(value)

    payload: dict[str, Any] = {
        "bytes_sent": _count("bytes_sent"),
        "bytes_recv": _count("bytes_recv"),
        "speed_up": _rate("speed_up"),
        "speed_down": _rate("speed_down"),
        "packets_sent": _count("packets_sent"),
        "packets_recv": _count("packets_recv"),
        "errin": _count("errin"),
        "errout": _count("errout"),
        "dropin": _count("dropin"),
        "dropout": _count("dropout"),
    }
    if "interfaces" in info:
        payload["interfaces"] = info["interfaces"]
    return payload


def _disk_payload(
    settings: SysmonConfig | None = None,
    info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _resolve_settings(settings)
    info = info if info is not None else collect("disk", cfg)
    primary_status = metric_status(
        info["percent"],
        cfg.thresholds.disk_warn,
        cfg.thresholds.disk_critical,
    )
    mounts = []
    for mount_info in info.get("mounts", []):
        percent = mount_info.get("percent", 0)
        mount_payload = {
            "mount": mount_info.get("mount", ""),
            "total": mount_info.get("total", 0),
            "used": mount_info.get("used", 0),
            "free": mount_info.get("free", 0),
            "percent": 0 if percent is None else percent,
            "status": metric_status(
                0 if percent is None else percent,
                cfg.thresholds.disk_warn,
                cfg.thresholds.disk_critical,
            ),
        }
        inode_percent = mount_info.get("inode_percent")
        if isinstance(inode_percent, (int, float)) and not isinstance(inode_percent, bool):
            mount_payload["inode_percent"] = float(inode_percent)
        mounts.append(mount_payload)
    payload = {
        "mounts": mounts,
        "mount": info["mount"],
        "total": info["total"],
        "used": info["used"],
        "free": info["free"],
        "percent": info["percent"],
        "read_bytes": info["read_bytes"],
        "write_bytes": info["write_bytes"],
        "read_speed": info["read_speed"],
        "write_speed": info["write_speed"],
        "status": primary_status,
    }
    inode_percent = info.get("inode_percent")
    if isinstance(inode_percent, (int, float)) and not isinstance(inode_percent, bool):
        payload["inode_percent"] = float(inode_percent)
    return payload


def _gpu_payload(
    settings: SysmonConfig | None = None,
    info: Optional[list[dict[str, Any]]] | object = _MISSING,
) -> Optional[list[dict[str, Any]]]:
    cfg = _resolve_settings(settings)
    gpus = collect("gpu", cfg) if info is _MISSING else info
    if not isinstance(gpus, list) or not gpus:
        return None

    def _number(gpu: dict[str, Any], key: str, default: float = 0.0) -> float:
        value = gpu.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return default
        return float(value)

    rows: list[dict[str, Any]] = []
    for gpu in gpus:
        if not isinstance(gpu, dict):
            continue
        temperature = gpu.get("temperature")
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            temperature_c = None
        else:
            temperature_c = float(temperature)
        rows.append(
            {
                "id": gpu.get("id", 0),
                "name": str(gpu.get("name") or "GPU"),
                "load": _number(gpu, "load"),
                "memory_total_mb": _number(gpu, "memory_total"),
                "memory_used_mb": _number(gpu, "memory_used"),
                "temperature_c": temperature_c,
                "backend": str(gpu.get("backend") or "unknown"),
            }
        )
    return rows or None


def _process_payload(
    name_filter: str | None = None,
    settings: SysmonConfig | None = None,
) -> list[dict[str, Any]]:
    cfg = _resolve_settings(settings)
    if name_filter is not None:
        from sysmon.collectors.registry import collect_processes

        rows = collect_processes(cfg, name_filter=name_filter)
    else:
        rows = collect("process", cfg)
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def collect_section(section: str, include_gpu: bool = True) -> dict[str, Any]:
    """Collect metrics for a single section."""
    if section == "cpu":
        payload: dict[str, Any] = {"cpu": _cpu_payload()}
    elif section == "memory":
        payload = {"memory": _memory_payload()}
    elif section == "network":
        payload = {"network": _network_payload()}
    elif section == "disk":
        payload = {"disk": _disk_payload()}
    elif section == "gpu":
        payload = {"gpu": _gpu_payload() if include_gpu else None}
    elif section == "process":
        payload = {"processes": _process_payload()}
    elif section == "sensors":
        payload = {"sensors": collect("sensors", _resolve_settings(None))}
    else:
        raise ValueError(f"Unknown section: {section}")
    payload["collected_at"] = time.time()
    return payload


def collect_brief(include_gpu: bool = True) -> dict[str, Any]:
    """Collect compact metrics for brief mode."""
    settings = load_config()
    data: dict[str, Any] = {}
    if settings.modules.cpu:
        data["cpu"] = _cpu_payload(settings)
    if settings.modules.memory:
        data["memory"] = _memory_payload(settings)
    if settings.modules.network:
        data["network"] = _network_payload(settings)
    if include_gpu and settings.modules.gpu and settings.enable_gpu:
        data["gpu"] = _gpu_payload(settings)
    if settings.modules.sensors:
        data["sensors"] = collect("sensors", settings)
    data["collected_at"] = time.time()
    return data


def _uptime_seconds() -> float | None:
    """Return uptime in seconds, or None when the boot time cannot be read."""
    try:
        import psutil

        boot_time = psutil.boot_time()
    except (OSError, RuntimeError, NotImplementedError, ImportError, AttributeError):
        return None
    return max(0.0, time.time() - float(boot_time))


def _snapshot_collected_at(snapshot: dict[str, Any]) -> float:
    """Use the collector timestamp when the snapshot has one."""
    timestamp = snapshot.get("timestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        return time.time()
    return float(timestamp)


def _store(data: dict[str, Any], key: str, producer: Any) -> None:
    """Store one section, recording a failure instead of aborting the payload."""
    try:
        data[key] = producer()
    except Exception as exc:
        errors = data.setdefault("errors", {})
        if isinstance(errors, dict):
            errors[key] = str(exc)


def collect_all(include_gpu: bool = True) -> dict[str, Any]:
    """Aggregate all metrics into a stable schema."""
    settings = load_config()
    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "sysmon_version": __version__,
        "host": platform.node(),
        "os": _get_os_name(),
        "arch": platform.machine(),
        "uptime": _get_uptime(),
        "collected_at": time.time(),
    }
    uptime_seconds = _uptime_seconds()
    if uptime_seconds is not None:
        data["uptime_seconds"] = uptime_seconds

    if settings.modules.cpu:
        _store(data, "cpu", lambda: _cpu_payload(settings))
    if settings.modules.memory:
        _store(data, "memory", lambda: _memory_payload(settings))
    if settings.modules.network:
        _store(data, "network", lambda: _network_payload(settings))
    if settings.modules.disk:
        _store(data, "disk", lambda: _disk_payload(settings))
    if settings.modules.gpu and include_gpu:
        _store(data, "gpu", lambda: _gpu_payload(settings))
    if settings.modules.process:
        _store(data, "processes", lambda: _process_payload(settings=settings))
    if settings.modules.sensors:
        _store(data, "sensors", lambda: collect("sensors", settings))

    return data


def collect_all_from_snapshot(
    snapshot: dict[str, Any],
    include_gpu: bool = True,
    settings: SysmonConfig | None = None,
) -> dict[str, Any]:
    """Build a schema v3 payload from a CollectorService snapshot."""
    cfg = _resolve_settings(settings)
    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "sysmon_version": __version__,
        "host": platform.node(),
        "os": _get_os_name(),
        "arch": platform.machine(),
        "uptime": _get_uptime(),
        "collected_at": _snapshot_collected_at(snapshot),
    }
    uptime_seconds = _uptime_seconds()
    if uptime_seconds is not None:
        data["uptime_seconds"] = uptime_seconds
    if cfg.modules.cpu and snapshot.get("cpu") is not None:
        _store(data, "cpu", lambda: _cpu_payload(cfg, info=snapshot["cpu"]))
    if cfg.modules.memory and snapshot.get("memory") is not None:
        _store(data, "memory", lambda: _memory_payload(cfg, info=snapshot["memory"]))
    if cfg.modules.network and snapshot.get("network") is not None:
        _store(data, "network", lambda: _network_payload(cfg, info=snapshot["network"]))
    if cfg.modules.disk and snapshot.get("disk") is not None:
        _store(data, "disk", lambda: _disk_payload(cfg, info=snapshot["disk"]))
    if cfg.modules.gpu and include_gpu and "gpu" in snapshot:
        _store(data, "gpu", lambda: _gpu_payload(cfg, info=snapshot["gpu"]))
    processes = snapshot.get("process", snapshot.get("processes"))
    if cfg.modules.process and processes is not None:
        data["processes"] = processes
    if cfg.modules.sensors and "sensors" in snapshot:
        data["sensors"] = snapshot["sensors"]
    return data


def to_json(data: dict[str, Any]) -> str:
    """Serialize metrics to pretty-printed JSON."""
    return json.dumps(data, ensure_ascii=False, indent=2)
