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
