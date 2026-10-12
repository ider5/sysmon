"""Tests for disk collector."""

from types import SimpleNamespace
from unittest.mock import patch

from sysmon.collectors import disk as disk_module
from sysmon.collectors.disk import get_disk_info


def test_inode_percent_from_statvfs(monkeypatch):
    stats = SimpleNamespace(f_files=100, f_ffree=25)
    monkeypatch.setattr(disk_module.os, "statvfs", lambda _mount: stats, raising=False)
    assert disk_module._inode_percent("/data") == 75.0


def test_inode_percent_ignores_non_numeric_counters(monkeypatch):
    stats = SimpleNamespace(f_files="bad", f_ffree=1)
    monkeypatch.setattr(disk_module.os, "statvfs", lambda _mount: stats, raising=False)
    assert disk_module._inode_percent("/data") is None


def test_inode_percent_missing_without_statvfs(monkeypatch):
    monkeypatch.delattr(disk_module.os, "statvfs", raising=False)
    assert disk_module._inode_percent("/") is None


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


def test_get_disk_info_when_io_counters_raise():
    usage = SimpleNamespace(total=100, used=40, free=60, percent=40.0)
    disk_module._prev_disk_io = None
    disk_module._prev_time = None
    with patch("sysmon.collectors.disk.psutil.disk_usage", return_value=usage):
        with patch(
            "sysmon.collectors.disk.psutil.disk_io_counters",
            side_effect=OSError("unavailable"),
        ):
            result = get_disk_info(mounts=["/data"])
    assert result["mount"] == "/data"
    assert result["percent"] == 40.0
    assert result["read_speed"] == 0.0
    assert result["read_bytes"] == 0
    assert disk_module._prev_disk_io is None


def test_get_disk_info_clamps_counter_reset():
    usage = SimpleNamespace(total=100, used=50, free=50, percent=50.0)
    first_io = SimpleNamespace(read_bytes=5000, write_bytes=4000)
    reset_io = SimpleNamespace(read_bytes=100, write_bytes=50)

    with patch("sysmon.collectors.disk.psutil.disk_usage", return_value=usage):
        with patch("sysmon.collectors.disk.psutil.disk_io_counters", return_value=first_io):
            with patch("sysmon.collectors.disk.time.time", return_value=0.0):
                get_disk_info()

        with patch("sysmon.collectors.disk.psutil.disk_io_counters", return_value=reset_io):
            with patch("sysmon.collectors.disk.time.time", return_value=2.0):
                result = get_disk_info()

    assert result["read_speed"] == 0.0
    assert result["write_speed"] == 0.0
