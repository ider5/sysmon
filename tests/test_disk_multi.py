"""Tests for multi-disk collector."""

from types import SimpleNamespace
from unittest.mock import patch

from sysmon.collectors.disk import get_disk_info, list_mount_points


def test_get_disk_info_includes_mounts_list():
    usage = SimpleNamespace(total=100, used=50, free=50, percent=50.0)
    io = SimpleNamespace(read_bytes=1000, write_bytes=2000)

    with patch("sysmon.collectors.disk.psutil.disk_usage", return_value=usage):
        with patch("sysmon.collectors.disk.psutil.disk_io_counters", return_value=io):
            with patch("sysmon.collectors.disk.time.time", return_value=1.0):
                result = get_disk_info(mounts=["/data"])

    assert "mounts" in result
    assert len(result["mounts"]) == 1
    assert result["mounts"][0]["mount"] == "/data"
    assert result["mount"] == "/data"


def test_list_mount_points_skips_inaccessible():
    parts = [
        SimpleNamespace(mountpoint="/", device="/dev/sda1"),
        SimpleNamespace(mountpoint="/bad", device="/dev/sdb1"),
    ]

    with patch("sysmon.collectors.disk.psutil.disk_partitions", return_value=parts):
        with patch(
            "sysmon.collectors.disk.psutil.disk_usage",
            side_effect=[SimpleNamespace(total=1, used=0, free=1, percent=0), OSError()],
        ):
            with patch("sysmon.collectors.disk.platform.system", return_value="Linux"):
                mounts = list_mount_points()

    assert mounts == ["/"]
