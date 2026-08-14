"""Tests for collector registry."""

import pytest

from sysmon.collectors import registry
from sysmon.collectors.registry import collect_named, list_collectors
from sysmon.config import SysmonConfig


def test_list_collectors_includes_builtins():
    names = list_collectors()
    assert "cpu" in names
    assert "memory" in names
    assert "network" in names
    assert "disk" in names
    assert "gpu" in names
    assert "process" in names
    assert "sensors" in names


def test_collect_named_cpu():
    data = collect_named("cpu")
    assert "percent" in data
    assert "cores" in data


def test_collect_named_unknown_raises():
    with pytest.raises(ValueError, match="Unknown collector"):
        collect_named("not-a-collector")


def test_collect_network_uses_supplied_settings(monkeypatch):
    captured = {}
    settings = SysmonConfig(network_interfaces=("eth0", "wlan0"))

    def _fake_get_network_info(interfaces):
        captured["interfaces"] = interfaces
        return {"source": "fake"}

    monkeypatch.setattr(
        "sysmon.collectors.network.get_network_info",
        _fake_get_network_info,
    )

    assert registry.collect("network", settings) == {"source": "fake"}
    assert captured["interfaces"] == settings.network_interfaces


def test_collect_unknown_raises():
    with pytest.raises(ValueError, match="Unknown collector"):
        registry.collect("unknown")


@pytest.mark.parametrize(
    "name",
    [
        "register_configured",
        "get_raw_collector",
        "collect_all_registered",
    ],
)
def test_legacy_registry_apis_are_removed(name):
    assert not hasattr(registry, name)
