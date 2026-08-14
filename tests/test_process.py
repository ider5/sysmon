"""Tests for process collector."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sysmon.collectors import process as process_module


@pytest.fixture(autouse=True)
def _disable_native_backend(monkeypatch):
    """Keep process_iter mocks from being skipped by an optional Rust backend."""
    monkeypatch.setattr(process_module, "_try_native_processes", lambda *a, **k: None)


def _proc(pid: int, cpu: float, mem: float, name: str) -> MagicMock:
    mock = MagicMock()
    mock.info = {
        "pid": pid,
        "name": name,
        "memory_percent": mem,
    }
    mock.pid = pid
    mock.memory_info.return_value = MagicMock(rss=mem * 1024 * 1024)
    mock.cpu_times.return_value = SimpleNamespace(user=cpu, system=0.0)
    mock.create_time.return_value = 1000.0 + pid
    return mock


def test_get_top_processes_requests_batch_attrs():
    with patch("sysmon.collectors.process.psutil.process_iter", return_value=[]) as mock_iter:
        process_module.get_top_processes(limit=2)
    mock_iter.assert_called_with(list(process_module.PROCESS_ITER_ATTRS))


def test_get_top_processes_sorts_by_cpu():
    procs = [
        _proc(1, 0.0, 5.0, "a"),
        _proc(2, 0.0, 2.0, "b"),
        _proc(3, 0.0, 8.0, "c"),
    ]

    with patch("sysmon.collectors.process.psutil.process_iter", return_value=procs):
        with patch("sysmon.collectors.process.time.monotonic", return_value=1.0):
            first = process_module.get_top_processes(limit=2, sort_by="cpu")
        assert all(item["cpu_percent"] == 0.0 for item in first)

        for mock, cpu in zip(procs, (0.1, 0.5, 0.3)):
            mock.cpu_times.return_value = SimpleNamespace(user=cpu, system=0.0)

        with patch("sysmon.collectors.process.time.monotonic", return_value=2.0):
            result = process_module.get_top_processes(limit=2, sort_by="cpu")

    assert len(result) == 2
    assert result[0]["pid"] == 2
    assert result[1]["pid"] == 3
    assert result[0]["cpu_percent"] == 50.0


def test_get_top_processes_name_filter():
    procs = [
        _proc(1, 10.0, 5.0, "chrome"),
        _proc(2, 50.0, 2.0, "python"),
        _proc(3, 30.0, 8.0, "Chrome Helper"),
    ]

    with patch("sysmon.collectors.process.psutil.process_iter", return_value=procs):
        result = process_module.get_top_processes(
            limit=10, sort_by="cpu", name_filter="chrome"
        )

    assert len(result) == 2
    names = {p["name"] for p in result}
    assert names == {"chrome", "Chrome Helper"}


def test_get_top_processes_sample_interval_computes_cpu(monkeypatch):
    proc = _proc(1, 0.0, 1.0, "a")
    proc.cpu_times.side_effect = [
        SimpleNamespace(user=0.0, system=0.0),
        SimpleNamespace(user=0.5, system=0.0),
    ]
    ticks = iter([1.0, 2.0])
    monkeypatch.setattr(process_module.time, "sleep", lambda _s: None)
    monkeypatch.setattr(process_module.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(
        process_module.psutil, "process_iter", lambda *a, **k: [proc]
    )

    result = process_module.get_top_processes(sample_interval=0.15)

    assert len(result) == 1
    assert result[0]["cpu_percent"] == 50.0


@pytest.mark.parametrize(
    "name,pid,expected",
    [
        ("System Idle Process", 0, True),
        ("Idle", 1, True),
        ("idle.exe", 4, True),
        ("System Interrupts", 2, True),
        ("swapper/0", 0, True),
        ("python.exe", 1234, False),
        ("browser_idle", 8, False),
        ("chrome", 0, True),
    ],
)
def test_is_idle_process(name, pid, expected):
    assert process_module.is_idle_process(name, pid) is expected


def test_get_top_processes_skips_idle_and_fills_limit():
    procs = [
        _proc(0, 0.0, 99.0, "System Idle Process"),
        _proc(1, 0.0, 80.0, "Idle"),
        _proc(2, 0.0, 10.0, "python"),
        _proc(3, 0.0, 20.0, "chrome"),
        _proc(4, 0.0, 15.0, "explorer"),
    ]
    with patch("sysmon.collectors.process.psutil.process_iter", return_value=procs):
        with patch("sysmon.collectors.process.time.monotonic", return_value=1.0):
            result = process_module.get_top_processes(limit=2, sort_by="memory")

    assert [item["name"] for item in result] == ["chrome", "explorer"]


def test_is_self_process(monkeypatch):
    monkeypatch.setattr(process_module.os, "getpid", lambda: 14260)
    assert process_module.is_self_process(14260) is True
    assert process_module.is_self_process(1) is False
    assert process_module.is_self_process(None) is False


def test_get_top_processes_skips_self_and_fills_limit(monkeypatch):
    monkeypatch.setattr(process_module.os, "getpid", lambda: 99)
    procs = [
        _proc(99, 0.0, 90.0, "python.exe"),
        _proc(3, 0.0, 20.0, "chrome"),
        _proc(4, 0.0, 15.0, "explorer"),
    ]
    with patch("sysmon.collectors.process.psutil.process_iter", return_value=procs):
        with patch("sysmon.collectors.process.time.monotonic", return_value=1.0):
            result = process_module.get_top_processes(limit=2, sort_by="memory")

    assert [item["name"] for item in result] == ["chrome", "explorer"]
