"""Structured data export for sysmon."""

from __future__ import annotations

import json
import platform
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
    status = metric_status(
        snapshot["percent"],
        cfg.thresholds.cpu_warn,
        cfg.thresholds.cpu_critical,
    )
    return {
        "percent": snapshot["percent"],
        "cores": snapshot["cores"],
        "count_logical": snapshot["count_logical"],
        "count_physical": snapshot["count_physical"],
        "freq_current_mhz": snapshot["freq_current"],
        "freq_max_mhz": snapshot["freq_max"],
        "status": status,
    }


def _memory_payload(
    settings: SysmonConfig | None = None,
    info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _resolve_settings(settings)
    info = info if info is not None else collect("memory", cfg)
    return {
        "total": info["total"],
        "used": info["used"],
        "available": info["available"],
        "percent": info["percent"],
        "swap_total": info["swap_total"],
        "swap_used": info["swap_used"],
        "swap_percent": info["swap_percent"],
        "status": metric_status(
            info["percent"],
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
    payload: dict[str, Any] = {
        "bytes_sent": info["bytes_sent"],
        "bytes_recv": info["bytes_recv"],
        "speed_up": info["speed_up"],
        "speed_down": info["speed_down"],
        "packets_sent": info["packets_sent"],
        "packets_recv": info["packets_recv"],
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
        mounts.append(
            {
                "mount": mount_info["mount"],
                "total": mount_info["total"],
                "used": mount_info["used"],
                "free": mount_info["free"],
                "percent": mount_info["percent"],
                "status": metric_status(
                    mount_info["percent"],
                    cfg.thresholds.disk_warn,
                    cfg.thresholds.disk_critical,
                ),
            }
        )
    return {
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


def _gpu_payload(
    settings: SysmonConfig | None = None,
    info: Optional[list[dict[str, Any]]] | object = _MISSING,
) -> Optional[list[dict[str, Any]]]:
    cfg = _resolve_settings(settings)
    gpus = collect("gpu", cfg) if info is _MISSING else info
    if not gpus:
        return None
    return [
        {
            "id": gpu["id"],
            "name": gpu["name"],
            "load": gpu["load"],
            "memory_total_mb": gpu["memory_total"],
            "memory_used_mb": gpu["memory_used"],
            "temperature_c": gpu["temperature"],
            "backend": gpu.get("backend", "unknown"),
        }
        for gpu in gpus
    ]


def _process_payload(
    name_filter: str | None = None,
    settings: SysmonConfig | None = None,
) -> list[dict[str, Any]]:
    cfg = _resolve_settings(settings)
    if name_filter is not None:
        from sysmon.collectors.registry import collect_processes

        return collect_processes(cfg, name_filter=name_filter)
    return collect("process", cfg)


def collect_section(section: str, include_gpu: bool = True) -> dict[str, Any]:
    """Collect metrics for a single section."""
    if section == "cpu":
        return {"cpu": _cpu_payload()}
    if section == "memory":
        return {"memory": _memory_payload()}
    if section == "network":
        return {"network": _network_payload()}
    if section == "disk":
        return {"disk": _disk_payload()}
    if section == "gpu":
        return {"gpu": _gpu_payload() if include_gpu else None}
    if section == "process":
        return {"processes": _process_payload()}
    raise ValueError(f"Unknown section: {section}")


def collect_brief(include_gpu: bool = True) -> dict[str, Any]:
    """Collect compact metrics for brief mode."""
    settings = load_config()
    data: dict[str, Any] = {
        "cpu": _cpu_payload(settings),
        "memory": _memory_payload(settings),
        "network": _network_payload(settings),
    }
    if include_gpu:
        data["gpu"] = _gpu_payload(settings)
    return data


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
    }

    if settings.modules.cpu:
        data["cpu"] = _cpu_payload(settings)
    if settings.modules.memory:
        data["memory"] = _memory_payload(settings)
    if settings.modules.network:
        data["network"] = _network_payload(settings)
    if settings.modules.disk:
        data["disk"] = _disk_payload(settings)
    if settings.modules.gpu and include_gpu:
        data["gpu"] = _gpu_payload(settings)
    if settings.modules.process:
        data["processes"] = _process_payload(settings=settings)
    if settings.modules.sensors:
        data["sensors"] = collect("sensors", settings)

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
    }
    if cfg.modules.cpu and snapshot.get("cpu") is not None:
        data["cpu"] = _cpu_payload(cfg, info=snapshot["cpu"])
    if cfg.modules.memory and snapshot.get("memory") is not None:
        data["memory"] = _memory_payload(cfg, info=snapshot["memory"])
    if cfg.modules.network and snapshot.get("network") is not None:
        data["network"] = _network_payload(cfg, info=snapshot["network"])
    if cfg.modules.disk and snapshot.get("disk") is not None:
        data["disk"] = _disk_payload(cfg, info=snapshot["disk"])
    if cfg.modules.gpu and include_gpu and "gpu" in snapshot:
        data["gpu"] = _gpu_payload(cfg, info=snapshot["gpu"])
    processes = snapshot.get("process", snapshot.get("processes"))
    if cfg.modules.process and processes is not None:
        data["processes"] = processes
    if cfg.modules.sensors and "sensors" in snapshot:
        data["sensors"] = snapshot["sensors"]
    return data


def to_json(data: dict[str, Any]) -> str:
    """Serialize metrics to pretty-printed JSON."""
    return json.dumps(data, ensure_ascii=False, indent=2)
