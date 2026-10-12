"""Tests for multi-network collector."""

from types import SimpleNamespace
from unittest.mock import patch

from sysmon.collectors import network as network_module
from sysmon.collectors.network import get_network_info, list_network_interfaces


def test_get_network_info_per_interface():
    aggregate = SimpleNamespace(
        bytes_sent=1000,
        bytes_recv=2000,
        packets_sent=10,
        packets_recv=20,
    )
    pernic_first = {
        "eth0": SimpleNamespace(
            bytes_sent=500, bytes_recv=1000, packets_sent=5, packets_recv=10,
        ),
    }
    pernic_second = {
        "eth0": SimpleNamespace(
            bytes_sent=1500, bytes_recv=3000, packets_sent=15, packets_recv=30,
        ),
    }

    network_module._prev_net_io = None
    network_module._prev_time = None
    network_module._prev_iface_io = {}
    network_module._prev_iface_time = None

    def mock_counters(pernic=False):
        if pernic:
            return pernic_first
        return aggregate

    with patch("sysmon.collectors.network.psutil.net_io_counters", side_effect=mock_counters):
        with patch("sysmon.collectors.network.time.time", return_value=0.0):
            first = get_network_info(interfaces=["eth0"])

    assert first["interfaces"][0]["speed_down"] == 0

    aggregate2 = SimpleNamespace(
        bytes_sent=2000, bytes_recv=4000, packets_sent=20, packets_recv=40,
    )

    def mock_counters_second(pernic=False):
        if pernic:
            return pernic_second
        return aggregate2

    with patch(
        "sysmon.collectors.network.psutil.net_io_counters",
        side_effect=mock_counters_second,
    ):
        with patch("sysmon.collectors.network.time.time", return_value=2.0):
            second = get_network_info(interfaces=["eth0"])

    assert "interfaces" in second
    assert second["interfaces"][0]["name"] == "eth0"
    assert second["interfaces"][0]["speed_down"] == 1000.0
    assert second["bytes_sent"] == 1500
    assert second["bytes_recv"] == 3000
    assert second["speed_down"] == 1000.0


def test_interface_includes_link_speed():
    pernic = {
        "eth0": SimpleNamespace(
            bytes_sent=1, bytes_recv=2, packets_sent=1, packets_recv=1,
            errin=0, errout=0, dropin=0, dropout=0,
        )
    }
    stats = {"eth0": SimpleNamespace(isup=True, speed=1000)}
    network_module._prev_iface_io = {}
    network_module._prev_iface_time = None
    with patch("sysmon.collectors.network.psutil.net_io_counters", return_value=pernic):
        with patch("sysmon.collectors.network.psutil.net_if_stats", return_value=stats):
            with patch("sysmon.collectors.network.time.time", return_value=1.0):
                result = get_network_info(interfaces=["eth0"])
    assert result["interfaces"][0]["speed_mbps"] == 1000


def test_non_finite_link_speed_is_omitted():
    pernic = {
        "bad0": SimpleNamespace(
            bytes_sent=1, bytes_recv=1, packets_sent=0, packets_recv=0,
            errin=0, errout=0, dropin=0, dropout=0,
        ),
        "eth0": SimpleNamespace(
            bytes_sent=1, bytes_recv=2, packets_sent=1, packets_recv=1,
            errin=0, errout=0, dropin=0, dropout=0,
        ),
    }
    stats = {
        "bad0": SimpleNamespace(isup=True, speed=float("inf")),
        "eth0": SimpleNamespace(isup=True, speed=1000),
    }
    network_module._prev_iface_io = {}
    network_module._prev_iface_time = None
    with patch("sysmon.collectors.network.psutil.net_io_counters", return_value=pernic):
        with patch("sysmon.collectors.network.psutil.net_if_stats", return_value=stats):
            with patch("sysmon.collectors.network.time.time", return_value=1.0):
                result = get_network_info(interfaces=["bad0", "eth0"])
    by_name = {item["name"]: item for item in result["interfaces"]}
    assert "speed_mbps" not in by_name["bad0"]
    assert by_name["eth0"]["speed_mbps"] == 1000


def test_interface_reports_link_down_without_speed():
    pernic = {
        "eth0": SimpleNamespace(
            bytes_sent=1, bytes_recv=1, packets_sent=0, packets_recv=0,
            errin=0, errout=0, dropin=0, dropout=0,
        )
    }
    stats = {"eth0": SimpleNamespace(isup=False, speed=0)}
    network_module._prev_iface_io = {}
    network_module._prev_iface_time = None
    with patch("sysmon.collectors.network.psutil.net_io_counters", return_value=pernic):
        with patch("sysmon.collectors.network.psutil.net_if_stats", return_value=stats):
            with patch("sysmon.collectors.network.time.time", return_value=1.0):
                result = get_network_info(interfaces=["eth0"])
    iface = result["interfaces"][0]
    assert iface["isup"] is False
    assert "speed_mbps" not in iface


def test_missing_interface_is_listed_at_zero():
    network_module._prev_iface_io = {"nope": SimpleNamespace(bytes_sent=5, bytes_recv=5)}
    network_module._prev_iface_time = 0.0

    with patch(
        "sysmon.collectors.network.psutil.net_io_counters",
        return_value={},
    ):
        with patch("sysmon.collectors.network.time.time", return_value=1.0):
            result = get_network_info(interfaces=["eth0", "nope"])

    assert [item["name"] for item in result["interfaces"]] == ["eth0", "nope"]
    assert result["bytes_sent"] == 0
    assert result["speed_down"] == 0.0
    assert "nope" not in network_module._prev_iface_io


def test_list_network_interfaces_when_stats_unavailable():
    with patch(
        "sysmon.collectors.network.psutil.net_if_stats",
        side_effect=OSError("stats"),
    ):
        assert list_network_interfaces() == []


def test_list_network_interfaces_excludes_loopback():
    stats = {
        "lo": SimpleNamespace(isup=True),
        "eth0": SimpleNamespace(isup=True),
        "docker0": SimpleNamespace(isup=False),
    }
    with patch("sysmon.collectors.network.psutil.net_if_stats", return_value=stats):
        names = list_network_interfaces()

    assert "lo" not in names
    assert "eth0" in names
    assert "docker0" not in names
