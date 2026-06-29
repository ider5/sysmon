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
