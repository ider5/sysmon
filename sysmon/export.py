"""Structured data export for sysmon."""

from __future__ import annotations

import json
import platform
from typing import Any, Optional

from sysmon import __version__
from sysmon.collectors.registry import collect_named
from sysmon.config import SysmonConfig, load_config, metric_status
from sysmon.display.components import _get_os_name, _get_uptime


def _resolve_settings(settings: SysmonConfig | None) -> SysmonConfig:
    return settings if settings is not None else load_config()


def _cpu_payload(settings: SysmonConfig | None = None) -> dict[str, Any]:
    snapshot = collect_named("cpu")
    cfg = _resolve_settings(settings)
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


def _memory_payload(settings: SysmonConfig | None = None) -> dict[str, Any]:
    info = collect_named("memory")
    cfg = _resolve_settings(settings)
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


def _network_payload(settings: SysmonConfig | None = None) -> dict[str, Any]:
    if settings is not None:
        from sysmon.collectors.network import get_network_info

        info = get_network_info(settings.network_interfaces)
    else:
        info = collect_named("network")
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


def _disk_payload(settings: SysmonConfig | None = None) -> dict[str, Any]:
    cfg = _resolve_settings(settings)
    if settings is not None:
        from sysmon.collectors.disk import get_disk_info

        info = get_disk_info(cfg.disk_mounts)
    else:
        info = collect_named("disk")
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


def _gpu_payload() -> Optional[list[dict[str, Any]]]:
    gpus = collect_named("gpu")
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
    from sysmon.collectors.process import get_top_processes

    return get_top_processes(
        limit=cfg.process_limit,
        name_filter=name_filter,
    )


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
        data["gpu"] = _gpu_payload()
    return data


def collect_all(include_gpu: bool = True) -> dict[str, Any]:
    """Aggregate all metrics into a stable schema."""
    settings = load_config()
    data: dict[str, Any] = {
        "schema_version": 3,
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
        data["gpu"] = _gpu_payload()
    if settings.modules.process:
        data["processes"] = _process_payload(settings=settings)

    return data


def to_json(data: dict[str, Any]) -> str:
    """Serialize metrics to pretty-printed JSON."""
    return json.dumps(data, ensure_ascii=False, indent=2)
