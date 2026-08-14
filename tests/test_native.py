"""Optional Rust process backend and Python fallback."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

from sysmon.collectors import process as process_module


def test_try_native_returns_none_when_core_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "sysmon._core", None)
    assert process_module._try_native_processes(10, "cpu", None) is None


def test_try_native_returns_none_when_backend_raises(monkeypatch):
    fake = ModuleType("sysmon._core")

    def boom(*_a, **_k):
        raise RuntimeError("native failed")

    fake.list_processes = boom
    monkeypatch.setitem(sys.modules, "sysmon._core", fake)
    assert process_module._try_native_processes(10, "cpu", None) is None


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


def test_native_backend_drops_idle_before_limit(monkeypatch):
    captured = {}

    def fake_list(limit, sort_by, name_filter):
        captured["limit"] = limit
        return [
            {
                "pid": 0,
                "name": "System Idle Process",
                "cpu_percent": 90.0,
                "memory_percent": 0.0,
                "memory_mb": 0.0,
            },
            {
                "pid": 8,
                "name": "python",
                "cpu_percent": 12.0,
                "memory_percent": 1.0,
                "memory_mb": 20.0,
            },
        ]

    fake = ModuleType("sysmon._core")
    fake.list_processes = fake_list
    monkeypatch.setitem(sys.modules, "sysmon._core", fake)
    result = process_module._try_native_processes(1, "cpu", None)
    assert captured["limit"] > 1
    assert [row["name"] for row in result] == ["python"]


def test_native_backend_drops_self_before_limit(monkeypatch):
    monkeypatch.setattr(process_module.os, "getpid", lambda: 14260)
    captured = {}

    def fake_list(limit, sort_by, name_filter):
        captured["limit"] = limit
        return [
            {
                "pid": 14260,
                "name": "python.exe",
                "cpu_percent": 61.8,
                "memory_percent": 0.3,
                "memory_mb": 45.0,
            },
            {
                "pid": 8,
                "name": "chrome",
                "cpu_percent": 12.0,
                "memory_percent": 1.0,
                "memory_mb": 20.0,
            },
        ]

    fake = ModuleType("sysmon._core")
    fake.list_processes = fake_list
    monkeypatch.setitem(sys.modules, "sysmon._core", fake)
    result = process_module._try_native_processes(1, "cpu", None)
    assert captured["limit"] > 1
    assert [row["name"] for row in result] == ["chrome"]


def test_try_native_calls_list_processes(monkeypatch):
    captured = {}
    fake = ModuleType("sysmon._core")

    def list_processes(limit, sort_by, name_filter):
        captured["args"] = (limit, sort_by, name_filter)
        return [{"pid": 1, "name": "a", "cpu_percent": 0.0, "memory_percent": 0.0, "memory_mb": 0.0}]

    fake.list_processes = list_processes
    monkeypatch.setitem(sys.modules, "sysmon._core", fake)
    result = process_module._try_native_processes(4, "memory", "chrome")
    assert captured["args"] == (
        4 + process_module.IDLE_FETCH_EXTRA,
        "memory",
        "chrome",
    )
    assert result[0]["pid"] == 1


def test_get_top_processes_sample_interval_uses_native(monkeypatch):
    calls = []

    def fake_native(limit, sort_by, name_filter):
        calls.append((limit, sort_by, name_filter))
        return [
            {
                "pid": 1,
                "name": "n",
                "cpu_percent": float(len(calls)),
                "memory_percent": 1.0,
                "memory_mb": 1.0,
            }
        ]

    monkeypatch.setattr(process_module, "_try_native_processes", fake_native)
    monkeypatch.setattr(process_module.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        process_module.psutil,
        "process_iter",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("psutil fallback")),
    )
    result = process_module.get_top_processes(sample_interval=0.15)
    assert len(calls) == 2
    assert result[0]["cpu_percent"] == 2.0


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


@pytest.mark.skipif(sys.platform != "linux", reason="sysinfo userland threads are Linux-specific")
def test_native_list_processes_skips_userland_threads():
    core = pytest.importorskip("sysmon._core")
    import psutil

    native_pids = {int(row["pid"]) for row in core.list_processes(50_000, "cpu", None)}
    psutil_pids = {proc.pid for proc in psutil.process_iter(["pid"])}
    extras = native_pids - psutil_pids

    userland_tids = []
    for pid in extras:
        try:
            with open(f"/proc/{pid}/status", encoding="utf-8") as handle:
                lines = handle.readlines()
        except OSError:
            continue
        tgid = None
        for line in lines:
            if line.startswith("Tgid:"):
                tgid = int(line.split()[1])
                break
        if tgid is not None and tgid != pid:
            userland_tids.append(pid)

    assert userland_tids == []
    assert len(native_pids) < len(psutil_pids) * 2


def test_native_sample_interval_sleeps_past_sysinfo_cpu_gate(monkeypatch):
    slept = []
    payload = [
        {
            "pid": 1,
            "name": "n",
            "cpu_percent": 1.0,
            "memory_percent": 1.0,
            "memory_mb": 1.0,
        }
    ]
    monkeypatch.setattr(process_module, "_try_native_processes", lambda *_a, **_k: payload)
    monkeypatch.setattr(process_module.time, "sleep", lambda seconds: slept.append(seconds))
    monkeypatch.setattr(
        process_module.psutil,
        "process_iter",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("psutil fallback")),
    )
    process_module.get_top_processes(sample_interval=0.15)
    assert slept
    assert slept[0] >= 0.25


def test_native_two_sample_reports_cpu_when_requested_interval_is_short():
    pytest.importorskip("sysmon._core")
    import subprocess
    import sys
    import time

    child = subprocess.Popen(
        [sys.executable, "-c", "while True: pass"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # Expire any CPU sample taken by earlier tests in this process.
        time.sleep(process_module.NATIVE_CPU_SAMPLE_FLOOR)
        rows = process_module.get_top_processes(limit=5_000, sample_interval=0.15)
        match = next((row for row in rows if row["pid"] == child.pid), None)
        assert match is not None
        assert match["cpu_percent"] > 10
    finally:
        child.kill()
        child.wait(timeout=1)
