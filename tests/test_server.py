"""Tests for localhost metrics server."""

from __future__ import annotations

import json
import threading
from http.client import HTTPConnection

from sysmon.server import format_prometheus, start_server

_FAKE_ALL = {
    "schema_version": 3,
    "cpu": {"percent": 12.5, "status": "ok"},
    "memory": {"percent": 40.0, "used": 1, "total": 2, "status": "ok"},
    "disk": {"percent": 50.0, "status": "ok"},
    "network": {"speed_up": 100.0, "speed_down": 200.0},
    "gpu": [
        {
            "id": 0,
            "name": "Fake",
            "load": 30.0,
            "memory_total_mb": 8192.0,
            "memory_used_mb": 1024.0,
        }
    ],
}


def test_format_prometheus_includes_core_gauges():
    text = format_prometheus(_FAKE_ALL)
    assert "sysmon_cpu_percent 12.5" in text
    assert "sysmon_memory_percent 40.0" in text
    assert "sysmon_disk_percent 50.0" in text
    assert "sysmon_gpu_load{id=\"0\"} 30.0" in text
    assert "# TYPE sysmon_cpu_percent gauge" in text


def test_format_prometheus_includes_mounts_and_interfaces():
    text = format_prometheus(
        {
            "disk": {
                "percent": 10.0,
                "mounts": [
                    {"mount": "C:\\", "percent": 11.0},
                    {"mount": "/", "percent": 22.5},
                ],
            },
            "network": {
                "speed_up": 5.0,
                "speed_down": 6.0,
                "interfaces": [
                    {"name": 'eth"0', "speed_up": 1.5, "speed_down": 2.5},
                ],
            },
        }
    )
    assert "sysmon_disk_percent 10.0" in text
    assert 'sysmon_disk_mount_percent{mount="C:\\\\"} 11.0' in text
    assert 'sysmon_disk_mount_percent{mount="/"} 22.5' in text
    assert text.count("# TYPE sysmon_disk_mount_percent gauge") == 1
    assert 'sysmon_network_interface_speed_up{device="eth\\"0"} 1.5' in text
    assert 'sysmon_network_interface_speed_down{device="eth\\"0"} 2.5' in text


def test_format_prometheus_includes_swap_when_present():
    text = format_prometheus(
        {
            "memory": {
                "percent": 40.0,
                "swap_percent": 12.5,
                "swap_used": 128.0,
                "swap_total": 1024.0,
            }
        }
    )
    assert "sysmon_memory_percent 40.0" in text
    assert "sysmon_swap_percent 12.5" in text
    assert "sysmon_swap_used_bytes 128.0" in text
    assert "sysmon_swap_total_bytes 1024.0" in text


def test_format_prometheus_omits_swap_when_absent():
    text = format_prometheus({"memory": {"percent": 40.0, "swap_total": 0, "swap_percent": 0}})
    assert "sysmon_swap_" not in text


def test_format_prometheus_includes_sensors():
    text = format_prometheus(
        {
            "sensors": {
                "battery": {"percent": 80.0, "power_plugged": False, "secsleft": None},
                "temperatures": {
                    "coretemp": [
                        {"label": 'Package "0"', "current": 45.5},
                        {"label": "skipped", "current": None},
                    ]
                },
            }
        }
    )
    assert "sysmon_battery_percent 80.0" in text
    assert "sysmon_battery_plugged 0.0" in text
    assert text.count("# TYPE sysmon_temperature_celsius gauge") == 1
    assert (
        'sysmon_temperature_celsius{sensor="coretemp",label="Package \\"0\\""} 45.5'
        in text
    )
    assert "skipped" not in text


def test_format_prometheus_omits_sensors_when_absent():
    assert "sysmon_battery" not in format_prometheus(_FAKE_ALL)
    assert "sysmon_temperature" not in format_prometheus(_FAKE_ALL)


def test_format_prometheus_includes_gpu_memory_and_temperature():
    text = format_prometheus(
        {
            "gpu": [
                {
                    "id": 0,
                    "load": 12.0,
                    "memory_used_mb": 512.0,
                    "memory_total_mb": 8192.0,
                    "temperature_c": 70.0,
                },
                {
                    "id": 1,
                    "load": 0.0,
                    "memory_used": 256.0,
                    "memory_total": 1024.0,
                    "temperature": None,
                },
            ]
        }
    )
    assert 'sysmon_gpu_load{id="0"} 12.0' in text
    assert 'sysmon_gpu_memory_used_mb{id="0"} 512.0' in text
    assert 'sysmon_gpu_memory_total_mb{id="1"} 1024.0' in text
    assert 'sysmon_gpu_temperature_celsius{id="0"} 70.0' in text
    assert 'sysmon_gpu_temperature_celsius{id="1"}' not in text
    assert text.count("# TYPE sysmon_gpu_load gauge") == 1


def test_format_prometheus_emits_gpu_metadata_once():
    data = {
        "gpu": [
            {"id": 0, "load": 10.0},
            {"id": 1, "load": 20.0},
        ]
    }
    text = format_prometheus(data)
    assert text.count("# TYPE sysmon_gpu_load gauge") == 1
    assert 'sysmon_gpu_load{id="0"} 10.0' in text
    assert 'sysmon_gpu_load{id="1"} 20.0' in text


def test_server_json_and_metrics_endpoints(monkeypatch):
    monkeypatch.setattr("sysmon.server.collect_all", lambda include_gpu=True: _FAKE_ALL)
    httpd = start_server("127.0.0.1", 0, payload_fn=lambda: _FAKE_ALL)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        port = httpd.server_address[1]
        conn = HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("GET", "/json")
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["schema_version"] == 3
        assert payload["cpu"]["percent"] == 12.5

        conn.request("GET", "/metrics")
        metrics = conn.getresponse()
        body = metrics.read().decode("utf-8")
        assert metrics.status == 200
        assert "sysmon_cpu_percent 12.5" in body
        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_start_server_binds_ipv6_loopback():
    import socket

    import pytest

    try:
        probe = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        probe.bind(("::1", 0))
        probe.close()
    except OSError:
        pytest.skip("IPv6 loopback is unavailable")

    httpd = start_server("::1", 0, payload_fn=lambda: {"schema_version": 3})
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        port = httpd.server_address[1]
        conn = HTTPConnection("::1", port, timeout=2)
        conn.request("GET", "/health")
        response = conn.getresponse()
        assert response.status == 200
        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_prime_rate_collectors_samples_network_and_disk(monkeypatch):
    from sysmon.config import SysmonConfig
    from sysmon.server import _prime_rate_collectors

    names = []
    slept = []
    monkeypatch.setattr(
        "sysmon.collectors.registry.collect",
        lambda name, settings=None: names.append(name),
    )
    monkeypatch.setattr("sysmon.server.time.sleep", lambda seconds: slept.append(seconds))
    _prime_rate_collectors(SysmonConfig(refresh_interval=2.0))
    assert names == ["network", "disk"]
    assert slept == [0.5]


def test_serve_forever_primes_before_starting_service(monkeypatch):
    from sysmon.server import serve_forever

    order = []

    class FakeService:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            order.append("start")

        def stop(self):
            order.append("stop")

        def get_snapshot(self):
            return {}

    class FakeHttpd:
        server_address = ("127.0.0.1", 9100)

        def serve_forever(self):
            order.append("serve")
            raise KeyboardInterrupt

        def shutdown(self):
            pass

        def server_close(self):
            pass

    monkeypatch.setattr(
        "sysmon.server._prime_rate_collectors",
        lambda _settings: order.append("prime"),
    )
    monkeypatch.setattr("sysmon.collectors.service.CollectorService", FakeService)
    monkeypatch.setattr("sysmon.server.start_server", lambda *_a, **_k: FakeHttpd())
    serve_forever(host="127.0.0.1", port=0)
    assert order[:2] == ["prime", "start"]
    assert "serve" in order
    assert "stop" in order
