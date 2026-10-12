"""Tests for memory helpers."""

from types import SimpleNamespace
from unittest.mock import patch

from sysmon.collectors.memory import bytes_to_gb, get_memory_info


def test_bytes_to_gb():
    assert bytes_to_gb(1024 ** 3) == "1.0"
    assert bytes_to_gb(2.5 * 1024 ** 3) == "2.5"
    assert bytes_to_gb(float("nan")) == "0.0"
    assert bytes_to_gb(None) == "0.0"


def test_get_memory_info_when_swap_is_unavailable():
    mem = SimpleNamespace(total=100, used=40, available=60, percent=40.0)
    with patch("sysmon.collectors.memory.psutil.virtual_memory", return_value=mem):
        with patch(
            "sysmon.collectors.memory.psutil.swap_memory",
            side_effect=NotImplementedError("swap"),
        ):
            info = get_memory_info()
    assert info["total"] == 100
    assert info["percent"] == 40.0
    assert info["swap_total"] == 0
    assert info["swap_percent"] == 0.0


def test_get_memory_info_ignores_non_numeric_fields():
    mem = SimpleNamespace(total=100, used="bad", available=60, percent=float("nan"))
    swap = SimpleNamespace(total=float("inf"), used=5, percent=None)
    with patch("sysmon.collectors.memory.psutil.virtual_memory", return_value=mem):
        with patch("sysmon.collectors.memory.psutil.swap_memory", return_value=swap):
            info = get_memory_info()
    assert info["total"] == 100.0
    assert info["used"] == 0.0
    assert info["percent"] == 0.0
    assert info["swap_total"] == 0.0
    assert info["swap_used"] == 5.0


def test_get_memory_info_when_memory_is_unavailable():
    with patch(
        "sysmon.collectors.memory.psutil.virtual_memory",
        side_effect=OSError("memory"),
    ):
        info = get_memory_info()
    assert info["total"] == 0
    assert info["percent"] == 0.0
    assert info["swap_total"] == 0
