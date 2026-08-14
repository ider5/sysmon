"""Tests for process collector."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sysmon.collectors import process as process_module


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
    return mock


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


def test_get_top_processes_sample_interval_sleeps(monkeypatch):
    slept = {}
    monkeypatch.setattr(process_module.time, "sleep", lambda s: slept.setdefault("s", s))
    monkeypatch.setattr(process_module.psutil, "process_iter", lambda *a, **k: [])
    process_module.get_top_processes(sample_interval=0.15)
    assert slept["s"] == 0.15
