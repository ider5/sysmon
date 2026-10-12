"""Tests for network formatting helpers."""

from types import SimpleNamespace
from unittest.mock import patch

from sysmon.collectors import network as network_module
from sysmon.collectors.network import format_bytes, format_speed, get_network_info


def test_error_counts_ignore_non_finite_values():
    counts = network_module._error_counts(
        SimpleNamespace(errin=float("inf"), errout=2, dropin=float("nan"), dropout=4)
    )
    assert counts == {"errin": 0, "errout": 2, "dropin": 0, "dropout": 4}


def test_format_bytes():
    assert format_bytes(512) == "512.0 B"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(1024 ** 3) == "1.0 GB"


def test_format_speed():
    assert format_speed(1024) == "1.0 KB/s"


def test_get_network_info_speed_calculation():
    first = SimpleNamespace(
        bytes_sent=1000, bytes_recv=2000, packets_sent=10, packets_recv=20,
    )
    second = SimpleNamespace(
        bytes_sent=2000, bytes_recv=4000, packets_sent=20, packets_recv=40,
    )

    network_module._prev_net_io = None
    network_module._prev_time = None

    with patch("sysmon.collectors.network.psutil.net_io_counters", return_value=first):
        with patch("sysmon.collectors.network.time.time", return_value=0.0):
            first_result = get_network_info()

    assert first_result["speed_up"] == 0
    assert first_result["speed_down"] == 0

    with patch("sysmon.collectors.network.psutil.net_io_counters", return_value=second):
        with patch("sysmon.collectors.network.time.time", return_value=2.0):
            second_result = get_network_info()

    assert second_result["speed_up"] == 500.0
    assert second_result["speed_down"] == 1000.0


def test_get_network_info_when_counters_unavailable():
    network_module._prev_net_io = None
    network_module._prev_time = None

    with patch("sysmon.collectors.network.psutil.net_io_counters", return_value=None):
        result = get_network_info()

    assert result == {
        "bytes_sent": 0,
        "bytes_recv": 0,
        "speed_up": 0.0,
        "speed_down": 0.0,
        "packets_sent": 0,
        "packets_recv": 0,
        "errin": 0,
        "errout": 0,
        "dropin": 0,
        "dropout": 0,
    }
    assert network_module._prev_net_io is None


def test_get_network_info_when_counters_raise():
    network_module._prev_net_io = None
    network_module._prev_time = None
    with patch(
        "sysmon.collectors.network.psutil.net_io_counters",
        side_effect=OSError("unavailable"),
    ):
        result = get_network_info()
    assert result["bytes_sent"] == 0
    assert result["speed_up"] == 0.0
    assert network_module._prev_net_io is None


def test_get_network_info_clamps_counter_reset():
    first = SimpleNamespace(
        bytes_sent=5000, bytes_recv=8000, packets_sent=10, packets_recv=20,
    )
    reset = SimpleNamespace(
        bytes_sent=10, bytes_recv=20, packets_sent=1, packets_recv=2,
    )

    with patch("sysmon.collectors.network.psutil.net_io_counters", return_value=first):
        with patch("sysmon.collectors.network.time.time", return_value=0.0):
            get_network_info()

    with patch("sysmon.collectors.network.psutil.net_io_counters", return_value=reset):
        with patch("sysmon.collectors.network.time.time", return_value=2.0):
            result = get_network_info()

    assert result["speed_up"] == 0.0
    assert result["speed_down"] == 0.0
