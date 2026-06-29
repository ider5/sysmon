"""Structured data export for sysmon."""

import json
import platform
from typing import Any, Optional

from sysmon import __version__
from sysmon.collectors.cpu import get_cpu_snapshot
from sysmon.collectors.disk import get_disk_info
from sysmon.collectors.gpu import get_gpu_info
from sysmon.collectors.memory import get_memory_info
from sysmon.collectors.network import get_network_info
from sysmon.display.components import _get_os_name, _get_uptime


def _cpu_payload() -> dict[str, Any]:
    snapshot = get_cpu_snapshot()
    return {
        "percent": snapshot["percent"],
        "cores": snapshot["cores"],
        "count_logical": snapshot["count_logical"],
        "count_physical": snapshot["count_physical"],
        "freq_current_mhz": snapshot["freq_current"],
        "freq_max_mhz": snapshot["freq_max"],
    }


def _memory_payload() -> dict[str, Any]:
    info = get_memory_info()
    return {
        "total": info["total"],
        "used": info["used"],
        "available": info["available"],
        "percent": info["percent"],
        "swap_total": info["swap_total"],
        "swap_used": info["swap_used"],
        "swap_percent": info["swap_percent"],
    }


def _network_payload() -> dict[str, Any]:
    info = get_network_info()
    return {
        "bytes_sent": info["bytes_sent"],
        "bytes_recv": info["bytes_recv"],
        "speed_up": info["speed_up"],
        "speed_down": info["speed_down"],
        "packets_sent": info["packets_sent"],
        "packets_recv": info["packets_recv"],
    }


def _disk_payload() -> dict[str, Any]:
    info = get_disk_info()
    return {
        "mount": info["mount"],
        "total": info["total"],
        "used": info["used"],
        "free": info["free"],
        "percent": info["percent"],
        "read_bytes": info["read_bytes"],
        "write_bytes": info["write_bytes"],
        "read_speed": info["read_speed"],
        "write_speed": info["write_speed"],
    }


def _gpu_payload() -> Optional[list[dict[str, Any]]]:
    gpus = get_gpu_info()
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
        }
        for gpu in gpus
    ]


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
        return {"gpu": _gpu_payload()}
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
    data: dict[str, Any] = {
        "schema_version": 1,
        "sysmon_version": __version__,
        "host": platform.node(),
        "os": _get_os_name(),
        "arch": platform.machine(),
        "uptime": _get_uptime(),
        "cpu": _cpu_payload(),
        "memory": _memory_payload(),
        "network": _network_payload(),
        "disk": _disk_payload(),
    }
    if include_gpu:
        data["gpu"] = _gpu_payload()
    return data


def to_json(data: dict[str, Any]) -> str:
    """Serialize metrics to pretty-printed JSON."""
    return json.dumps(data, ensure_ascii=False, indent=2)
