"""Tests for optional sensors collector."""

from __future__ import annotations

from types import SimpleNamespace

from sysmon.collectors import sensors as sensors_mod
from sysmon.collectors.registry import collect, list_collectors
from sysmon.config import ModuleConfig, SysmonConfig
from sysmon.export import collect_all


def test_sensors_default_disabled():
    config = SysmonConfig()
    assert config.modules.sensors is False


def test_from_mapping_sensors_opt_in():
    config = SysmonConfig.from_mapping({"modules": {"sensors": True}})
    assert config.modules.sensors is True


def test_sensors_registered():
    assert "sensors" in list_collectors()


def test_get_sensors_info_maps_psutil(monkeypatch):
    monkeypatch.setattr(
        sensors_mod.psutil,
        "sensors_battery",
        lambda: SimpleNamespace(percent=80.0, secsleft=3600, power_plugged=False),
        raising=False,
    )
    monkeypatch.setattr(
        sensors_mod.psutil,
        "sensors_temperatures",
        lambda: {
            "coretemp": [
                SimpleNamespace(label="Package", current=45.0, high=80.0, critical=100.0)
            ]
        },
        raising=False,
    )
    info = sensors_mod.get_sensors_info()
    assert info["battery"]["percent"] == 80.0
    assert info["battery"]["power_plugged"] is False
    assert info["temperatures"]["coretemp"][0]["label"] == "Package"
    assert info["temperatures"]["coretemp"][0]["current"] == 45.0


def test_get_sensors_info_without_temperature_api(monkeypatch):
    monkeypatch.setattr(
        sensors_mod.psutil,
        "sensors_battery",
        lambda: SimpleNamespace(percent=50.0, secsleft=-1, power_plugged=True),
        raising=False,
    )
    monkeypatch.delattr(sensors_mod.psutil, "sensors_temperatures", raising=False)
    info = sensors_mod.get_sensors_info()
    assert info["battery"]["percent"] == 50.0
    assert info["temperatures"] == {}


def test_collect_all_omits_sensors_by_default(monkeypatch):
    monkeypatch.setattr("sysmon.export.load_config", lambda: SysmonConfig())
    data = collect_all(include_gpu=False)
    assert "sensors" not in data
    assert data["schema_version"] == 3


def test_collect_all_includes_sensors_when_enabled(monkeypatch):
    settings = SysmonConfig(modules=ModuleConfig(sensors=True))
    monkeypatch.setattr("sysmon.export.load_config", lambda: settings)
    monkeypatch.setattr(
        "sysmon.collectors.sensors.get_sensors_info",
        lambda: {"battery": None, "temperatures": {}},
    )
    data = collect_all(include_gpu=False)
    assert data["schema_version"] == 3
    assert data["sensors"] == {"battery": None, "temperatures": {}}


def test_collect_sensors_uses_registry(monkeypatch):
    payload = {"battery": None, "temperatures": {}}
    monkeypatch.setattr(sensors_mod, "get_sensors_info", lambda: payload)
    assert collect("sensors", SysmonConfig()) == payload
