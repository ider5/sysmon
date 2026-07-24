"""Tests for structured JSON export."""

import json

from sysmon.export import (
    collect_all,
    collect_brief,
    collect_section,
    to_json,
)


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


def test_collect_brief_keys():
    data = collect_brief(include_gpu=False)
    assert set(data.keys()) == {"cpu", "memory", "network"}


def test_collect_section_cpu():
    data = collect_section("cpu")
    assert "cpu" in data
    assert "percent" in data["cpu"]


def test_collect_section_unknown_raises():
    import pytest

    with pytest.raises(ValueError, match="Unknown section"):
        collect_section("invalid")


def test_to_json_roundtrip():
    data = collect_brief(include_gpu=False)
    parsed = json.loads(to_json(data))
    assert parsed == data
