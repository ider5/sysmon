"""Collector plugin registry for sysmon."""

from __future__ import annotations

from typing import Any, Callable

from sysmon.config import SysmonConfig, load_config

CollectorFn = Callable[[SysmonConfig], Any]

_REGISTRY: dict[str, CollectorFn] = {}


def register(name: str, fn: CollectorFn) -> None:
    """Register a collector by name."""
    _REGISTRY[name] = fn


def get_collector(name: str) -> CollectorFn | None:
    """Get a registered collector function."""
    return _REGISTRY.get(name)


def list_collectors() -> list[str]:
    """Return registered collector names."""
    return list(_REGISTRY.keys())


def collect(name: str, settings: SysmonConfig | None = None) -> Any:
    """Collect metrics for a named collector."""
    fn = _REGISTRY.get(name)
    if fn is None:
        raise ValueError(f"Unknown collector: {name}")
    if settings is None:
        settings = load_config()
    return fn(settings)


def collect_named(name: str) -> Any:
    """Collect metrics for a named collector."""
    return collect(name)


def collect_processes(
    settings: SysmonConfig | None = None,
    *,
    limit: int | None = None,
    sort_by: str = "cpu",
    name_filter: str | None = None,
    sample_interval: float | None = None,
) -> Any:
    """Collect top processes, honoring extra sort/filter arguments."""
    cfg = settings if settings is not None else load_config()
    from sysmon.collectors.process import get_top_processes

    return get_top_processes(
        limit=cfg.process_limit if limit is None else limit,
        sort_by=sort_by,
        name_filter=name_filter,
        sample_interval=sample_interval,
    )


def _collect_cpu(settings: SysmonConfig) -> Any:
    from sysmon.collectors.cpu import get_cpu_snapshot

    return get_cpu_snapshot()


def _collect_memory(settings: SysmonConfig) -> Any:
    from sysmon.collectors.memory import get_memory_info

    return get_memory_info()


def _collect_network(settings: SysmonConfig) -> Any:
    from sysmon.collectors.network import get_network_info

    return get_network_info(settings.network_interfaces)


def _collect_disk(settings: SysmonConfig) -> Any:
    from sysmon.collectors.disk import get_disk_info

    return get_disk_info(settings.disk_mounts)


def _collect_gpu(settings: SysmonConfig) -> Any:
    from sysmon.collectors.gpu import get_gpu_info

    return get_gpu_info()


def _collect_process(settings: SysmonConfig) -> Any:
    return collect_processes(settings)


def _collect_sensors(settings: SysmonConfig) -> Any:
    from sysmon.collectors.sensors import get_sensors_info

    return get_sensors_info()


def _register_builtins() -> None:
    register("cpu", _collect_cpu)
    register("memory", _collect_memory)
    register("network", _collect_network)
    register("disk", _collect_disk)
    register("gpu", _collect_gpu)
    register("process", _collect_process)
    register("sensors", _collect_sensors)


_register_builtins()
