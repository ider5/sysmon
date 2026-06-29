"""Tests for collector registry."""

from sysmon.collectors.registry import collect_named, list_collectors


def test_list_collectors_includes_builtins():
    names = list_collectors()
    assert "cpu" in names
    assert "memory" in names
    assert "network" in names
    assert "disk" in names
    assert "gpu" in names
    assert "process" in names


def test_collect_named_cpu():
    data = collect_named("cpu")
    assert "percent" in data
    assert "cores" in data
