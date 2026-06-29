"""Structured data export for sysmon."""

from __future__ import annotations

import json
import platform
from typing import Any, Optional

from sysmon import __version__
from sysmon.collectors.registry import collect_named
from sysmon.config import load_config, metric_status
from sysmon.display.components import _get_os_name, _get_uptime


def _cpu_payload() -> dict[str, Any]:
    snapshot = collect_named("cpu")
    settings = load_config()
    status = metric_status(
        snapshot["percent"],
        settings.thresholds.cpu_warn,
        settings.thresholds.cpu_critical,
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


def _memory_payload() -> dict[str, Any]:
    info = collect_named("memory")
    settings = load_config()
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
            settings.thresholds.memory_warn,
            settings.thresholds.memory_critical,
        ),
    }


def _network_payload() -> dict[str, Any]:
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


def _disk_payload() -> dict[str, Any]:
    info = collect_named("disk")
    settings = load_config()
    primary_status = metric_status(
        info["percent"],
        settings.thresholds.disk_warn,
        settings.thresholds.disk_critical,
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
                    settings.thresholds.disk_warn,
                    settings.thresholds.disk_critical,
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


def _process_payload(name_filter: str | None = None) -> list[dict[str, Any]]:
    settings = load_config()
    from sysmon.collectors.process import get_top_processes

    return get_top_processes(
        limit=settings.process_limit,
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
    data: dict[str, Any] = {
        "cpu": _cpu_payload(),
        "memory": _memory_payload(),
        "network": _network_payload(),
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
        data["cpu"] = _cpu_payload()
    if settings.modules.memory:
        data["memory"] = _memory_payload()
    if settings.modules.network:
        data["network"] = _network_payload()
    if settings.modules.disk:
        data["disk"] = _disk_payload()
    if settings.modules.gpu and include_gpu:
        data["gpu"] = _gpu_payload()
    if settings.modules.process:
        data["processes"] = _process_payload()

    return data


def to_json(data: dict[str, Any]) -> str:
    """Serialize metrics to pretty-printed JSON."""
    return json.dumps(data, ensure_ascii=False, indent=2)
