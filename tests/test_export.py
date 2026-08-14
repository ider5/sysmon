"""Tests for structured JSON export."""

import json

import pytest

from sysmon.collectors import registry
from sysmon.config import DEFAULT_CONFIG
from sysmon.export import (
    SCHEMA_VERSION,
    collect_all,
    collect_all_from_snapshot,
    collect_brief,
    collect_section,
    to_json,
)

_FAKE_GPU = {
    "id": 0,
    "name": "FakeGPU",
    "load": 12.5,
    "memory_total": 8192.0,
    "memory_used": 1024.0,
    "temperature": 48.0,
    "backend": "mock",
}


def test_collect_all_schema():
    data = collect_all(include_gpu=False)
    assert data["schema_version"] == SCHEMA_VERSION
    assert "sysmon_version" in data
    assert "host" in data
    assert "os" in data
    assert "arch" in data
    assert "uptime" in data
    assert "cpu" in data
    assert "memory" in data
    assert "network" in data
    assert "disk" in data
    assert "gpu" not in data


def test_collect_all_cpu_payload():
    cpu = collect_all(include_gpu=False)["cpu"]
    assert "percent" in cpu
    assert "cores" in cpu
    assert "status" in cpu
    assert cpu["status"] in ("ok", "warn", "critical")


def test_collect_all_loads_config_once(monkeypatch):
    calls = {"count": 0}

    def _counting_load_config():
        calls["count"] += 1
        return DEFAULT_CONFIG

    monkeypatch.setattr("sysmon.export.load_config", _counting_load_config)
    collect_all(include_gpu=False)
    assert calls["count"] == 1


def test_collect_brief_loads_config_once(monkeypatch):
    calls = {"count": 0}

    def _counting_load_config():
        calls["count"] += 1
        return DEFAULT_CONFIG

    monkeypatch.setattr("sysmon.export.load_config", _counting_load_config)
    collect_brief(include_gpu=False)
    assert calls["count"] == 1


def test_collect_brief_keys():
    data = collect_brief(include_gpu=False)
    assert set(data.keys()) == {"cpu", "memory", "network"}


def test_collect_section_cpu():
    data = collect_section("cpu")
    assert "cpu" in data
    assert "percent" in data["cpu"]


def test_collect_section_memory():
    data = collect_section("memory")
    assert "memory" in data
    assert "percent" in data["memory"]
    assert data["memory"]["status"] in ("ok", "warn", "critical")


def test_collect_section_network():
    data = collect_section("network")
    assert "network" in data
    assert "bytes_sent" in data["network"]
    assert "speed_down" in data["network"]


def test_collect_section_disk():
    data = collect_section("disk")
    assert "disk" in data
    assert "percent" in data["disk"]
    assert "mounts" in data["disk"]
    assert data["disk"]["status"] in ("ok", "warn", "critical")


def test_collect_section_process():
    data = collect_section("process")
    assert "processes" in data
    assert isinstance(data["processes"], list)


def test_collect_section_gpu_with_mock(monkeypatch):
    monkeypatch.setitem(registry._REGISTRY, "gpu", lambda _settings: [_FAKE_GPU])
    data = collect_section("gpu")
    assert data["gpu"] is not None
    assert len(data["gpu"]) == 1
    assert data["gpu"][0]["name"] == "FakeGPU"
    assert data["gpu"][0]["memory_total_mb"] == 8192.0
    assert data["gpu"][0]["backend"] == "mock"


def test_collect_section_gpu_none(monkeypatch):
    monkeypatch.setitem(registry._REGISTRY, "gpu", lambda _settings: None)
    data = collect_section("gpu")
    assert data["gpu"] is None


def test_collect_section_gpu_disabled():
    data = collect_section("gpu", include_gpu=False)
    assert data["gpu"] is None


def test_collect_all_gpu_with_mock(monkeypatch):
    monkeypatch.setitem(registry._REGISTRY, "gpu", lambda _settings: [_FAKE_GPU])
    data = collect_all(include_gpu=True)
    assert data["gpu"] is not None
    assert data["gpu"][0]["name"] == "FakeGPU"


def test_collect_all_respects_disabled_modules(monkeypatch):
    from sysmon.config import ModuleConfig, SysmonConfig

    settings = SysmonConfig(
        modules=ModuleConfig(
            cpu=True,
            memory=False,
            network=False,
            disk=False,
            gpu=False,
            process=False,
        )
    )
    monkeypatch.setattr("sysmon.export.load_config", lambda: settings)
    data = collect_all(include_gpu=True)
    assert "cpu" in data
    assert "memory" not in data
    assert "network" not in data
    assert "disk" not in data
    assert "gpu" not in data
    assert "processes" not in data


def test_collect_section_unknown_raises():
    with pytest.raises(ValueError, match="Unknown section"):
        collect_section("invalid")


def test_to_json_roundtrip():
    data = collect_brief(include_gpu=False)
    parsed = json.loads(to_json(data))
    assert parsed == data


def _cpu_stub(_settings=None):
    return {
        "percent": 10.0,
        "cores": [10.0],
        "count_logical": 1,
        "count_physical": 1,
        "freq_current": 1000.0,
        "freq_max": 2000.0,
    }


def _memory_stub(_settings=None):
    return {
        "total": 8,
        "used": 4,
        "available": 4,
        "percent": 50.0,
        "swap_total": 1,
        "swap_used": 0,
        "swap_percent": 0.0,
    }


def _network_stub(_settings=None):
    return {
        "bytes_sent": 1,
        "bytes_recv": 2,
        "speed_up": 0.0,
        "speed_down": 0.0,
        "packets_sent": 0,
        "packets_recv": 0,
    }


def _disk_stub(_settings=None):
    return {
        "mounts": [],
        "mount": "/",
        "total": 1,
        "used": 1,
        "free": 0,
        "percent": 10.0,
        "read_bytes": 0,
        "write_bytes": 0,
        "read_speed": 0.0,
        "write_speed": 0.0,
    }


_COLLECT_STUBS = {
    "cpu": _cpu_stub,
    "memory": _memory_stub,
    "network": _network_stub,
    "disk": _disk_stub,
    "gpu": lambda _settings=None: [_FAKE_GPU],
    "process": lambda _settings=None: [],
}


def _patch_export_collect(monkeypatch, fake_collect):
    monkeypatch.setattr("sysmon.export.collect", fake_collect)


def test_collect_all_passes_same_settings_to_registry_collect(monkeypatch):
    from sysmon.config import SysmonConfig

    settings = SysmonConfig()
    monkeypatch.setattr("sysmon.export.load_config", lambda: settings)
    calls = []

    def fake_collect(name, collect_settings=None):
        calls.append((name, collect_settings))
        return _COLLECT_STUBS[name](collect_settings)

    _patch_export_collect(monkeypatch, fake_collect)

    collect_all(include_gpu=True)

    assert [name for name, _settings in calls] == [
        "cpu",
        "memory",
        "network",
        "disk",
        "gpu",
        "process",
    ]
    assert all(collect_settings is settings for _name, collect_settings in calls)


def test_collect_brief_passes_same_settings_to_registry_collect(monkeypatch):
    from sysmon.config import SysmonConfig

    settings = SysmonConfig()
    monkeypatch.setattr("sysmon.export.load_config", lambda: settings)
    calls = []

    def fake_collect(name, collect_settings=None):
        calls.append((name, collect_settings))
        return _COLLECT_STUBS[name](collect_settings)

    _patch_export_collect(monkeypatch, fake_collect)

    collect_brief(include_gpu=True)

    assert [name for name, _settings in calls] == ["cpu", "memory", "network", "gpu"]
    assert all(collect_settings is settings for _name, collect_settings in calls)


@pytest.mark.parametrize(
    "section,collector_name",
    [
        ("cpu", "cpu"),
        ("memory", "memory"),
        ("network", "network"),
        ("disk", "disk"),
        ("gpu", "gpu"),
        ("process", "process"),
    ],
)
def test_collect_section_passes_resolved_settings_to_collect(
    monkeypatch, section, collector_name
):
    from sysmon.config import SysmonConfig

    settings = SysmonConfig()
    monkeypatch.setattr("sysmon.export.load_config", lambda: settings)
    calls = []

    def fake_collect(name, collect_settings=None):
        calls.append((name, collect_settings))
        return _COLLECT_STUBS[name](collect_settings)

    _patch_export_collect(monkeypatch, fake_collect)

    collect_section(section)

    assert calls == [(collector_name, settings)]


def test_process_payload_with_name_filter_calls_get_top_processes(monkeypatch):
    from sysmon.config import SysmonConfig
    from sysmon.export import _process_payload

    settings = SysmonConfig(process_limit=3)
    collect_calls = []
    process_calls = []

    def fake_collect(name, collect_settings=None):
        collect_calls.append((name, collect_settings))
        return []

    def fake_get_top_processes(limit=10, name_filter=None, **_kwargs):
        process_calls.append((limit, name_filter))
        return [{"pid": 1, "name": "chrome"}]

    _patch_export_collect(monkeypatch, fake_collect)
    monkeypatch.setattr(
        "sysmon.collectors.process.get_top_processes",
        fake_get_top_processes,
    )

    result = _process_payload(name_filter="chrome", settings=settings)

    assert collect_calls == []
    assert process_calls == [(3, "chrome")]
    assert result == [{"pid": 1, "name": "chrome"}]


def test_collect_all_from_snapshot_maps_collector_fields():
    from sysmon.config import ModuleConfig, SysmonConfig

    snapshot = {
        "cpu": _cpu_stub(),
        "memory": _memory_stub(),
        "network": _network_stub(),
        "disk": _disk_stub(),
        "gpu": [_FAKE_GPU],
        "process": [
            {
                "pid": 9,
                "name": "proc",
                "cpu_percent": 1.5,
                "memory_percent": 2.0,
                "memory_mb": 3.0,
            }
        ],
        "sensors": {"battery_percent": 80.0, "temperatures": []},
    }
    settings = SysmonConfig(modules=ModuleConfig(sensors=True))
    data = collect_all_from_snapshot(snapshot, include_gpu=True, settings=settings)
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["cpu"]["freq_current_mhz"] == 1000.0
    assert data["cpu"]["freq_max_mhz"] == 2000.0
    assert "freq_current" not in data["cpu"]
    assert data["gpu"][0]["memory_total_mb"] == 8192.0
    assert data["gpu"][0]["memory_used_mb"] == 1024.0
    assert data["gpu"][0]["temperature_c"] == 48.0
    assert "memory_total" not in data["gpu"][0]
    assert data["processes"][0]["pid"] == 9
    assert "process" not in data
    assert data["sensors"]["battery_percent"] == 80.0
