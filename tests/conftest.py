"""Shared pytest fixtures for sysmon tests."""

from __future__ import annotations

import pytest

from sysmon.config import clear_config_cache


@pytest.fixture(autouse=True)
def _clear_config_cache_between_tests():
    """Keep load_config cache from leaking across tests that swap paths."""
    clear_config_cache()
    yield
    clear_config_cache()


@pytest.fixture(autouse=True)
def _reset_collector_globals():
    """Reset module-level collector caches so tests stay isolated."""
    from sysmon.collectors import disk as disk_module
    from sysmon.collectors import gpu as gpu_module
    from sysmon.collectors import network as network_module
    from sysmon.collectors import process as process_module

    disk_module._prev_disk_io = None
    disk_module._prev_time = None
    network_module._prev_net_io = None
    network_module._prev_time = None
    network_module._prev_iface_io = {}
    network_module._prev_iface_time = None
    process_module.clear_process_cpu_cache()
    gpu_module.reset_nvml_state_for_tests()
    yield
    disk_module._prev_disk_io = None
    disk_module._prev_time = None
    network_module._prev_net_io = None
    network_module._prev_time = None
    network_module._prev_iface_io = {}
    network_module._prev_iface_time = None
    process_module.clear_process_cpu_cache()
    gpu_module.reset_nvml_state_for_tests()
