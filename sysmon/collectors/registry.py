"""Collector plugin registry for sysmon."""

from __future__ import annotations

from typing import Any, Callable, Protocol

CollectorFn = Callable[[], Any]

_RAW: dict[str, CollectorFn] = {}
_REGISTRY: dict[str, CollectorFn] = {}


class Collector(Protocol):
    """Protocol for metric collectors."""

    name: str

    def collect(self) -> Any:
        """Return collected metrics."""


def register(name: str, fn: CollectorFn) -> None:
    """Register a collector by name."""
    _RAW[name] = fn
    _REGISTRY[name] = fn


def register_configured(name: str, fn: CollectorFn) -> None:
    """Register a config-aware wrapper while keeping the raw collector."""
    _RAW[name] = fn
    _REGISTRY[name] = fn


def get_collector(name: str) -> CollectorFn | None:
    """Get a registered collector function."""
    return _REGISTRY.get(name)


def get_raw_collector(name: str) -> CollectorFn | None:
    """Get the underlying collector without config wrappers."""
    return _RAW.get(name)


def list_collectors() -> list[str]:
    """Return registered collector names."""
    return list(_REGISTRY.keys())


def collect_named(name: str) -> Any:
    """Collect metrics for a named collector."""
    fn = _REGISTRY.get(name)
    if fn is None:
        raise ValueError(f"Unknown collector: {name}")
    return fn()


def collect_all_registered(
    names: list[str] | None = None,
    include_gpu: bool = True,
) -> dict[str, Any]:
    """Collect metrics from all or selected registered collectors."""
    selected = names if names is not None else list_collectors()
    result: dict[str, Any] = {}
    for name in selected:
        if name == "gpu" and not include_gpu:
            continue
        if name in _REGISTRY:
            result[name] = _REGISTRY[name]()
    return result


def _collect_disk() -> Any:
    from sysmon.collectors.disk import get_disk_info
    from sysmon.config import load_config

    settings = load_config()
    return get_disk_info(settings.disk_mounts)


def _collect_network() -> Any:
    from sysmon.collectors.network import get_network_info
    from sysmon.config import load_config

    settings = load_config()
    return get_network_info(settings.network_interfaces)


def _collect_process() -> Any:
    from sysmon.collectors.process import get_top_processes
    from sysmon.config import load_config

    settings = load_config()
    return get_top_processes(limit=settings.process_limit)


def _register_builtins() -> None:
    from sysmon.collectors.cpu import get_cpu_snapshot
    from sysmon.collectors.gpu import get_gpu_info
    from sysmon.collectors.memory import get_memory_info

    register("cpu", get_cpu_snapshot)
    register("memory", get_memory_info)
    register_configured("network", _collect_network)
    register_configured("disk", _collect_disk)
    register("gpu", get_gpu_info)
    register_configured("process", _collect_process)


_register_builtins()
