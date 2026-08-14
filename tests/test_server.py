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


def test_server_json_and_metrics_endpoints(monkeypatch):
    monkeypatch.setattr("sysmon.server.collect_all", lambda include_gpu=True: _FAKE_ALL)
    httpd = start_server("127.0.0.1", 0)
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
