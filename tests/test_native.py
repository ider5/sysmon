"""Optional Rust process backend and Python fallback."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

from sysmon.collectors import process as process_module


def test_try_native_returns_none_when_core_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "sysmon._core", None)
    assert process_module._try_native_processes(10, "cpu", None, None) is None


def test_try_native_skipped_when_sample_interval_required(monkeypatch):
    fake = ModuleType("sysmon._core")

    def boom(*_a, **_k):
        raise AssertionError("native backend should not run during one-shot sampling")

    fake.list_processes = boom
    monkeypatch.setitem(sys.modules, "sysmon._core", fake)
    assert process_module._try_native_processes(10, "cpu", None, 0.2) is None


def test_try_native_returns_none_when_backend_raises(monkeypatch):
    fake = ModuleType("sysmon._core")

    def boom(*_a, **_k):
        raise RuntimeError("native failed")

    fake.list_processes = boom
    monkeypatch.setitem(sys.modules, "sysmon._core", fake)
    assert process_module._try_native_processes(10, "cpu", None, None) is None


def test_get_top_processes_uses_native_when_available(monkeypatch):
    payload = [
        {
            "pid": 7,
            "name": "native",
            "cpu_percent": 1.5,
            "memory_percent": 2.5,
            "memory_mb": 3.5,
        }
    ]
    monkeypatch.setattr(
        process_module,
        "_try_native_processes",
        lambda *a, **k: payload,
    )
    monkeypatch.setattr(
        process_module.psutil,
        "process_iter",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("psutil fallback")),
    )
    assert process_module.get_top_processes(limit=3) == payload


def test_try_native_calls_list_processes(monkeypatch):
    captured = {}
    fake = ModuleType("sysmon._core")

    def list_processes(limit, sort_by, name_filter):
        captured["args"] = (limit, sort_by, name_filter)
        return [{"pid": 1, "name": "a", "cpu_percent": 0.0, "memory_percent": 0.0, "memory_mb": 0.0}]

    fake.list_processes = list_processes
    monkeypatch.setitem(sys.modules, "sysmon._core", fake)
    result = process_module._try_native_processes(4, "memory", "chrome", None)
    assert captured["args"] == (4, "memory", "chrome")
    assert result[0]["pid"] == 1


def test_native_list_processes_payload_shape():
    core = pytest.importorskip("sysmon._core")
    rows = core.list_processes(5, "cpu", None)
    assert isinstance(rows, list)
    for row in rows:
        assert set(row) >= {
            "pid",
            "name",
            "cpu_percent",
            "memory_percent",
            "memory_mb",
        }
        assert isinstance(row["pid"], int)
        assert isinstance(row["name"], str)


def test_native_list_processes_name_filter():
    core = pytest.importorskip("sysmon._core")
    rows = core.list_processes(50, "cpu", "this-name-should-not-match-zzzz")
    assert rows == []
