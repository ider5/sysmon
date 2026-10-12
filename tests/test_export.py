"""Tests for structured JSON export."""

import json
import time

import pytest

from sysmon.collectors import registry
from sysmon.config import DEFAULT_CONFIG, ModuleConfig, SysmonConfig
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
    assert set(data.keys()) == {"cpu", "memory", "network", "collected_at"}


def test_collect_brief_respects_modules(monkeypatch):
    from sysmon.config import ModuleConfig, SysmonConfig

    settings = SysmonConfig(
        modules=ModuleConfig(
            cpu=False,
            memory=False,
            network=False,
            disk=False,
            gpu=True,
            process=False,
            sensors=True,
        ),
        enable_gpu=False,
    )
    monkeypatch.setattr("sysmon.export.load_config", lambda: settings)
    monkeypatch.setattr(
        "sysmon.export.collect",
        lambda name, collect_settings=None: {
            "battery": {"percent": 12.0, "power_plugged": False, "secsleft": None},
            "temperatures": {},
        },
    )
    data = collect_brief(include_gpu=True)
    assert set(data) == {"sensors", "collected_at"}
    assert data["sensors"]["battery"]["percent"] == 12.0


def test_collect_brief_sensors_include_hottest_temperature(monkeypatch):
    from sysmon.config import ModuleConfig, SysmonConfig

    settings = SysmonConfig(
        modules=ModuleConfig(
            cpu=False,
            memory=False,
            network=False,
            disk=False,
            gpu=False,
            process=False,
            sensors=True,
        )
    )
    monkeypatch.setattr("sysmon.export.load_config", lambda: settings)
    monkeypatch.setattr(
        "sysmon.export.collect",
        lambda *_a, **_k: {
            "battery": None,
            "temperatures": {"cpu": [{"label": "pkg", "current": 62.0}]},
        },
    )
    data = collect_brief(include_gpu=False)
    assert data["sensors"]["hottest_c"] == 62.0


def test_gpu_payload_tolerates_partial_record(monkeypatch):
    monkeypatch.setattr(
        "sysmon.export.collect",
        lambda *_a, **_k: [{"load": 12.5, "temperature": 0}],
    )
    data = collect_section("gpu")
    gpu = data["gpu"][0]
    assert gpu["load"] == 12.5
    assert gpu["name"] == "GPU"
    assert gpu["memory_used_mb"] == 0.0
    assert gpu["temperature_c"] == 0.0


def test_gpu_payload_hides_negative_temperature(monkeypatch):
    monkeypatch.setattr(
        "sysmon.export.collect",
        lambda *_a, **_k: [{"load": 1, "temperature": -1}],
    )
    data = collect_section("gpu")
    assert data["gpu"][0]["temperature_c"] is None


def test_cpu_and_memory_payloads_tolerate_partial_records(monkeypatch):
    def fake_collect(name, settings=None):
        if name == "cpu":
            return {"percent": 12.5}
        if name == "memory":
            return {"percent": 40.0, "total": 100}
        raise AssertionError(name)

    monkeypatch.setattr("sysmon.export.collect", fake_collect)
    cpu = collect_section("cpu")["cpu"]
    memory = collect_section("memory")["memory"]
    assert cpu["percent"] == 12.5
    assert cpu["cores"] == []
    assert cpu["freq_current_mhz"] == 0.0
    assert memory["percent"] == 40.0
    assert memory["used"] == 0
    assert memory["swap_total"] == 0


def test_cpu_payload_includes_load_average(monkeypatch):
    monkeypatch.setattr(
        "sysmon.export.collect",
        lambda *_a, **_k: {
            "percent": 1.0,
            "cores": [1.0],
            "count_logical": 2,
            "count_physical": 1,
            "freq_current": 0,
            "freq_max": 0,
            "load_avg": (0.1, 0.2, 0.3),
        },
    )
    data = collect_section("cpu")
    assert data["cpu"]["load_avg"] == [0.1, 0.2, 0.3]


def test_metric_sections_tolerate_non_record(monkeypatch):
    monkeypatch.setattr("sysmon.export.collect", lambda *_a, **_k: "bad")
    cpu = collect_section("cpu")
    memory = collect_section("memory")
    network = collect_section("network")
    assert cpu["cpu"]["percent"] == 0.0
    assert cpu["cpu"]["cores"] == []
    assert memory["memory"]["percent"] == 0.0
    assert network["network"]["bytes_sent"] == 0
    assert "errors" not in cpu


def test_collect_section_cpu():
    data = collect_section("cpu")
    assert "cpu" in data
    assert "percent" in data["cpu"]


def test_collect_section_memory():
    data = collect_section("memory")
    assert "memory" in data
    assert "percent" in data["memory"]
    assert data["memory"]["status"] in ("ok", "warn", "critical")


def test_network_payload_tolerates_partial_record(monkeypatch):
    monkeypatch.setattr("sysmon.export.collect", lambda *_a, **_k: {"bytes_sent": 5})
    data = collect_section("network")
    assert data["network"]["bytes_sent"] == 5
    assert data["network"]["speed_down"] == 0.0
    assert data["network"]["errin"] == 0


def test_network_payload_drops_non_record_interfaces(monkeypatch):
    monkeypatch.setattr(
        "sysmon.export.collect",
        lambda *_a, **_k: {
            "bytes_sent": 1,
            "interfaces": [None, {"name": "eth0", "isup": False}, "bad"],
        },
    )
    data = collect_section("network")
    assert data["network"]["interfaces"] == [{"name": "eth0", "isup": False}]


def test_collect_section_network():
    data = collect_section("network")
    assert "network" in data
    assert "bytes_sent" in data["network"]
    assert "speed_down" in data["network"]


def test_disk_payload_tolerates_partial_mount(monkeypatch):
    monkeypatch.setattr(
        "sysmon.export.collect",
        lambda *_a, **_k: {
            "mount": "/",
            "percent": 10.0,
            "total": 100,
            "used": 10,
            "free": 90,
            "read_bytes": 0,
            "write_bytes": 0,
            "read_speed": 0,
            "write_speed": 0,
            "mounts": [{"mount": "/data", "percent": 5.0}],
        },
    )
    data = collect_section("disk")
    mount = data["disk"]["mounts"][0]
    assert mount["mount"] == "/data"
    assert mount["free"] == 0
    assert mount["percent"] == 5.0


def test_disk_payload_tolerates_partial_primary(monkeypatch):
    monkeypatch.setattr(
        "sysmon.export.collect",
        lambda *_a, **_k: {
            "mounts": ["bad", {"mount": "/data", "percent": 5.0}, None],
        },
    )
    data = collect_section("disk")
    disk = data["disk"]
    assert disk["mount"] == ""
    assert disk["percent"] == 0.0
    assert disk["read_speed"] == 0.0
    assert disk["total"] == 0
    assert [mount["mount"] for mount in disk["mounts"]] == ["/data"]
    assert "errors" not in data


def test_collect_section_disk():
    data = collect_section("disk")
    assert "disk" in data
    assert "percent" in data["disk"]
    assert "mounts" in data["disk"]
    assert data["disk"]["status"] in ("ok", "warn", "critical")


def test_process_payload_drops_non_records(monkeypatch):
    monkeypatch.setattr(
        "sysmon.export.collect",
        lambda *_a, **_k: [None, {"pid": 1, "name": "a"}, "bad"],
    )
    data = collect_section("process")
    assert data["processes"] == [{"pid": 1, "name": "a"}]


def test_snapshot_processes_drop_non_records():
    from sysmon.config import ModuleConfig, SysmonConfig

    settings = SysmonConfig(modules=ModuleConfig(process=True, sensors=False))
    data = collect_all_from_snapshot(
        {"process": [None, {"pid": 4, "name": "ok"}, "bad"]},
        include_gpu=False,
        settings=settings,
    )
    assert data["processes"] == [{"pid": 4, "name": "ok"}]
    missing = collect_all_from_snapshot(
        {"process": "unavailable"},
        include_gpu=False,
        settings=settings,
    )
    assert missing["processes"] == []


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


def test_collect_all_isolates_section_errors(monkeypatch):
    from sysmon.config import ModuleConfig, SysmonConfig

    settings = SysmonConfig(
        modules=ModuleConfig(
            cpu=True,
            memory=True,
            network=False,
            disk=False,
            gpu=False,
            process=False,
            sensors=False,
        )
    )
    monkeypatch.setattr("sysmon.export.load_config", lambda: settings)
    monkeypatch.setattr(
        "sysmon.export._cpu_payload",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("cpu down")),
    )
    data = collect_all(include_gpu=False)
    assert "cpu" not in data
    assert data["errors"]["cpu"] == "cpu down"
    assert "percent" in data["memory"]


def test_collect_all_from_snapshot_uses_collector_timestamp():
    settings = SysmonConfig(
        modules=ModuleConfig(
            cpu=False,
            memory=False,
            network=False,
            disk=False,
            gpu=False,
            process=False,
            sensors=False,
        )
    )
    data = collect_all_from_snapshot(
        {"timestamp": 123.5},
        include_gpu=False,
        settings=settings,
    )
    assert data["collected_at"] == 123.5


def test_snapshot_preserves_collector_errors():
    settings = SysmonConfig(
        modules=ModuleConfig(
            cpu=True,
            memory=False,
            network=False,
            disk=False,
            gpu=False,
            process=False,
            sensors=False,
        )
    )
    data = collect_all_from_snapshot(
        {"timestamp": 10.0, "errors": {"cpu": "cpu down"}},
        include_gpu=False,
        settings=settings,
    )
    assert data["errors"]["cpu"] == "cpu down"
    assert "cpu" not in data


def test_snapshot_errors_do_not_hide_formatting_errors(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("format")

    monkeypatch.setattr("sysmon.export._cpu_payload", boom)
    settings = SysmonConfig(
        modules=ModuleConfig(
            cpu=True,
            memory=False,
            network=False,
            disk=False,
            gpu=False,
            process=False,
            sensors=False,
        )
    )
    data = collect_all_from_snapshot(
        {"cpu": {"percent": 1}, "errors": {"disk": "disk down"}},
        include_gpu=False,
        settings=settings,
    )
    assert data["errors"]["cpu"] == "format"
    assert data["errors"]["disk"] == "disk down"


def test_snapshot_collected_at_ignores_non_finite(monkeypatch):
    monkeypatch.setattr("sysmon.export.time.time", lambda: 1000.0)
    settings = SysmonConfig(
        modules=ModuleConfig(
            cpu=False,
            memory=False,
            network=False,
            disk=False,
            gpu=False,
            process=False,
            sensors=False,
        )
    )
    data = collect_all_from_snapshot(
        {"timestamp": float("inf")},
        include_gpu=False,
        settings=settings,
    )
    assert data["collected_at"] == 1000.0


def test_collect_all_includes_boot_time(monkeypatch):
    boot = time.time() - 125
    monkeypatch.setattr("psutil.boot_time", lambda: boot)
    data = collect_all(include_gpu=False)
    assert data["boot_time"] == pytest.approx(boot)
    assert 120 <= data["uptime_seconds"] <= 130


def test_collect_all_includes_uptime_seconds(monkeypatch):
    monkeypatch.setattr("psutil.boot_time", lambda: time.time() - 125)
    data = collect_all(include_gpu=False)
    assert 120 <= data["uptime_seconds"] <= 130


def test_collect_all_includes_collected_at():
    before = time.time()
    data = collect_all(include_gpu=False)
    assert before <= data["collected_at"] <= time.time()


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


def test_snapshot_sensors_include_hottest_temperature():
    settings = SysmonConfig(modules=ModuleConfig(sensors=True))
    data = collect_all_from_snapshot(
        {
            "sensors": {
                "battery": None,
                "temperatures": {"cpu": [{"label": "pkg", "current": 61.0}]},
            }
        },
        include_gpu=False,
        settings=settings,
    )
    assert data["sensors"]["hottest_c"] == 61.0


def test_sensors_payload_includes_hottest_temperature(monkeypatch):
    monkeypatch.setattr(
        "sysmon.export.collect",
        lambda *_a, **_k: {
            "battery": None,
            "temperatures": {
                "coretemp": [
                    {"label": "a", "current": 40.0},
                    {"label": "b", "current": 55.5},
                ]
            },
        },
    )
    data = collect_section("sensors")
    assert data["sensors"]["hottest_c"] == 55.5


def test_collect_section_sensors(monkeypatch):
    payload = {"battery": None, "temperatures": {"coretemp": []}}

    def fake_collect(name, settings=None):
        assert name == "sensors"
        return payload

    monkeypatch.setattr("sysmon.export.collect", fake_collect)
    data = collect_section("sensors")
    assert data["sensors"] == payload
    assert isinstance(data["collected_at"], float)


def test_to_json_replaces_non_finite_numbers():
    parsed = json.loads(
        to_json(
            {
                "cpu": {"percent": float("nan"), "load_avg": (1.0, float("inf"), 0.25)},
                "ok": 1,
                "flag": True,
            }
        )
    )
    assert parsed["cpu"]["percent"] is None
    assert parsed["cpu"]["load_avg"] == [1.0, None, 0.25]
    assert parsed["ok"] == 1
    assert parsed["flag"] is True


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
