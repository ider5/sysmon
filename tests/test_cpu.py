"""Tests for CPU snapshot collector."""

from unittest.mock import patch

from sysmon.collectors.cpu import get_cpu_snapshot


def test_get_cpu_snapshot_overall_from_cores():
    with patch("sysmon.collectors.cpu.psutil.cpu_percent", return_value=[20.0, 40.0, 60.0, 80.0]):
        with patch("sysmon.collectors.cpu.psutil.cpu_count", side_effect=[4, 2]):
            with patch("sysmon.collectors.cpu.platform.system", return_value="Linux"):
                with patch("sysmon.collectors.cpu.psutil.cpu_freq", return_value=None):
                    snapshot = get_cpu_snapshot(interval=0)

    assert snapshot["percent"] == 50.0
    assert snapshot["cores"] == [20.0, 40.0, 60.0, 80.0]
    assert snapshot["count_logical"] == 4
    assert snapshot["count_physical"] == 2
