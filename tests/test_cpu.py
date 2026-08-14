"""Tests for CPU snapshot collector."""

from unittest.mock import patch

from sysmon.collectors import cpu as cpu_mod
from sysmon.collectors.cpu import get_cpu_snapshot


def test_get_cpu_snapshot_overall_from_cores():
    with patch("sysmon.collectors.cpu.psutil.cpu_percent", return_value=[20.0, 40.0, 60.0, 80.0]):
        with patch("sysmon.collectors.cpu.psutil.cpu_count", side_effect=[4, 2]):
            with patch("sysmon.collectors.cpu.platform.system", return_value="Linux"):
                with patch(
                    "sysmon.collectors.cpu.psutil.cpu_freq",
                    return_value=None,
                    create=True,
                ):
                    snapshot = get_cpu_snapshot(interval=0)

    assert snapshot["percent"] == 50.0
    assert snapshot["cores"] == [20.0, 40.0, 60.0, 80.0]
    assert snapshot["count_logical"] == 4
    assert snapshot["count_physical"] == 2


def test_get_freq_fields_when_cpu_freq_missing(monkeypatch):
    monkeypatch.setattr(cpu_mod.platform, "system", lambda: "Darwin")
    monkeypatch.delattr(cpu_mod.psutil, "cpu_freq", raising=False)
    assert cpu_mod._get_freq_fields() == (0.0, 0.0)


def test_ensure_freq_collector_skips_thread_on_non_windows(monkeypatch):
    monkeypatch.setattr(cpu_mod, "_collector_started", False)
    monkeypatch.setattr(cpu_mod.platform, "system", lambda: "Linux")
    with patch("sysmon.collectors.cpu.threading.Thread") as mock_thread:
        cpu_mod._ensure_freq_collector()
        mock_thread.assert_not_called()
