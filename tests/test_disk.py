"""Tests for disk collector."""

from types import SimpleNamespace
from unittest.mock import patch

from sysmon.collectors import disk as disk_module
from sysmon.collectors.disk import get_disk_info


def test_get_disk_info_speed_calculation():
    usage = SimpleNamespace(total=100, used=50, free=50, percent=50.0)
    first_io = SimpleNamespace(read_bytes=1000, write_bytes=2000)
    second_io = SimpleNamespace(read_bytes=3000, write_bytes=5000)

    disk_module._prev_disk_io = None
    disk_module._prev_time = None

    with patch("sysmon.collectors.disk.psutil.disk_usage", return_value=usage):
        with patch("sysmon.collectors.disk.psutil.disk_io_counters", return_value=first_io):
            with patch("sysmon.collectors.disk.time.time", return_value=0.0):
                first_result = get_disk_info()

    assert first_result["read_speed"] == 0
    assert first_result["write_speed"] == 0

    with patch("sysmon.collectors.disk.psutil.disk_usage", return_value=usage):
        with patch("sysmon.collectors.disk.psutil.disk_io_counters", return_value=second_io):
            with patch("sysmon.collectors.disk.time.time", return_value=2.0):
                second_result = get_disk_info()

    assert second_result["read_speed"] == 1000.0
    assert second_result["write_speed"] == 1500.0
