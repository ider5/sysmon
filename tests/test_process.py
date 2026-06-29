"""Tests for process collector."""

from unittest.mock import MagicMock, patch


def test_get_top_processes_sorts_by_cpu():
    procs = []
    for pid, cpu, mem, name in [
        (1, 10.0, 5.0, "a"),
        (2, 50.0, 2.0, "b"),
        (3, 30.0, 8.0, "c"),
    ]:
        mock = MagicMock()
        mock.info = {
            "pid": pid,
            "name": name,
            "cpu_percent": cpu,
            "memory_percent": mem,
        }
        mock.memory_info.return_value = MagicMock(rss=mem * 1024 * 1024)
        procs.append(mock)

    with patch("sysmon.collectors.process.psutil.process_iter", return_value=procs):
        from sysmon.collectors.process import get_top_processes

        result = get_top_processes(limit=2, sort_by="cpu")

    assert len(result) == 2
    assert result[0]["pid"] == 2
    assert result[1]["pid"] == 3
