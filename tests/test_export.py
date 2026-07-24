"""Tests for structured JSON export."""

import json

import pytest

from sysmon.collectors import registry
from sysmon.config import DEFAULT_CONFIG
from sysmon.export import (
    collect_all,
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
    assert data["schema_version"] == 3
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


def test_collect_section_gpu_with_mock(monkeypatch):
    monkeypatch.setitem(registry._REGISTRY, "gpu", lambda: [_FAKE_GPU])
    data = collect_section("gpu")
    assert data["gpu"] is not None
    assert len(data["gpu"]) == 1
    assert data["gpu"][0]["name"] == "FakeGPU"
    assert data["gpu"][0]["memory_total_mb"] == 8192.0
    assert data["gpu"][0]["backend"] == "mock"


def test_collect_section_gpu_none(monkeypatch):
    monkeypatch.setitem(registry._REGISTRY, "gpu", lambda: None)
    data = collect_section("gpu")
    assert data["gpu"] is None


def test_collect_section_gpu_disabled():
    data = collect_section("gpu", include_gpu=False)
    assert data["gpu"] is None


def test_collect_all_gpu_with_mock(monkeypatch):
    monkeypatch.setitem(registry._REGISTRY, "gpu", lambda: [_FAKE_GPU])
    data = collect_all(include_gpu=True)
    assert data["gpu"] is not None
    assert data["gpu"][0]["name"] == "FakeGPU"


def test_collect_section_unknown_raises():
    with pytest.raises(ValueError, match="Unknown section"):
        collect_section("invalid")


def test_to_json_roundtrip():
    data = collect_brief(include_gpu=False)
    parsed = json.loads(to_json(data))
    assert parsed == data
