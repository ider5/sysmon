"""Tests for localhost metrics server."""

from __future__ import annotations

import json
import threading
import time
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


def test_format_prometheus_counts_section_errors():
    text = format_prometheus({"errors": {"cpu": "down", "disk": "down"}})
    assert "sysmon_section_errors 2.0" in text
    assert "sysmon_section_errors" not in format_prometheus({})


def test_format_prometheus_includes_sample_age():
    text = format_prometheus({"collected_at": time.time() - 5})
    ages = [
        float(line.split()[-1])
        for line in text.splitlines()
        if line.startswith("sysmon_sample_age_seconds ")
    ]
    assert ages
    assert ages[0] >= 4.0


def test_format_prometheus_includes_collected_at():
    text = format_prometheus({"collected_at": 100.5, "cpu": {"percent": 1.0}})
    assert "sysmon_collected_at_seconds 100.5" in text


def test_format_prometheus_includes_boot_time():
    text = format_prometheus({"boot_time": 1700000000})
    assert "sysmon_boot_time_seconds 1700000000.0" in text


def test_format_prometheus_includes_uptime():
    text = format_prometheus({"uptime_seconds": 125})
    assert "sysmon_uptime_seconds 125.0" in text


def test_format_prometheus_includes_cpu_counts():
    text = format_prometheus(
        {"cpu": {"percent": 10.0, "count_logical": 8, "count_physical": 4}}
    )
    assert "sysmon_cpu_logical 8.0" in text
    assert "sysmon_cpu_physical 4.0" in text


def test_format_prometheus_includes_load_average():
    text = format_prometheus({"cpu": {"percent": 10.0, "load_avg": [1.0, 0.5, 0.25]}})
    assert 'sysmon_load_average{window="1m"} 1.0' in text
    assert 'sysmon_load_average{window="5m"} 0.5' in text
    assert 'sysmon_load_average{window="15m"} 0.25' in text
    assert text.count("# TYPE sysmon_load_average gauge") == 1


def test_format_prometheus_skips_non_finite_labeled_samples():
    text = format_prometheus(
        {
            "cpu": {"percent": 10.0, "load_avg": [1.0, float("inf"), 0.25]},
            "disk": {
                "percent": 10.0,
                "mounts": [
                    {"mount": "/bad", "percent": float("nan"), "inode_percent": float("inf")},
                    {"mount": "/", "percent": 40.0, "inode_percent": 5.0},
                ],
            },
            "network": {
                "interfaces": [
                    {"name": "bad0", "speed_up": True, "speed_down": float("nan")},
                    {"name": "eth0", "speed_up": 100.0, "speed_down": 200.0},
                ]
            },
            "sensors": {
                "temperatures": {
                    "coretemp": [
                        {"label": "bad", "current": True},
                        {"label": "hot", "current": float("inf")},
                        {"label": "pkg", "current": 61.0},
                    ]
                }
            },
        }
    )
    assert 'sysmon_load_average{window="1m"} 1.0' in text
    assert 'sysmon_load_average{window="15m"} 0.25' in text
    assert 'window="5m"' not in text
    assert 'sysmon_disk_mount_percent{mount="/"} 40.0' in text
    assert 'mount="/bad"' not in text
    assert "sysmon_disk_mount_inode_percent" in text
    assert 'sysmon_network_interface_speed_up{device="eth0"} 100.0' in text
    assert 'device="bad0"' not in text
    assert 'sysmon_temperature_celsius{sensor="coretemp",label="pkg"} 61.0' in text
    for line in text.splitlines():
        if line.startswith("#") or not line:
            continue
        assert line.rsplit(" ", 1)[-1] not in {"inf", "-inf", "nan"}


def test_format_prometheus_skips_non_numeric_values():
    text = format_prometheus(
        {"cpu": {"percent": None}, "disk": {"percent": float("nan"), "read_bytes": "nope"}}
    )
    assert "sysmon_cpu_percent" not in text
    assert "sysmon_disk_percent" not in text
    assert "sysmon_disk_read_bytes" not in text
    assert "sysmon_up 1.0" in text


def test_format_prometheus_includes_build_info():
    from sysmon import __version__

    text = format_prometheus({})
    assert f'sysmon_info{{version="{__version__}"}} 1.0' in text


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


def test_format_prometheus_includes_link_speed():
    text = format_prometheus(
        {
            "network": {
                "interfaces": [{"name": "eth0", "speed_mbps": 1000}],
            }
        }
    )
    assert 'sysmon_network_interface_speed_mbps{device="eth0"} 1000.0' in text


def test_format_prometheus_includes_process_sample():
    text = format_prometheus(
        {
            "processes": [
                {"pid": 1, "cpu_percent": 10.0, "memory_percent": 80.0},
                "bad",
                {"pid": 2, "cpu_percent": 40.0, "memory_percent": 5.0},
                {"pid": 3, "cpu_percent": float("nan")},
            ]
        }
    )
    assert "sysmon_process_count 3.0" in text
    assert "sysmon_process_top_cpu_percent 40.0" in text
    assert "sysmon_process_top_memory_percent 80.0" in text
    empty = format_prometheus({"processes": []})
    assert "sysmon_process_count 0.0" in empty
    assert "sysmon_process_top_cpu_percent" not in empty
    assert "sysmon_process_top_memory_percent" not in empty


def test_format_prometheus_includes_link_state():
    text = format_prometheus(
        {
            "network": {
                "interfaces": [
                    {"name": "eth0", "isup": False},
                    {"name": "wlan0", "isup": True},
                    {"name": "skip0"},
                ]
            }
        }
    )
    assert 'sysmon_network_interface_up{device="eth0"} 0.0' in text
    assert 'sysmon_network_interface_up{device="wlan0"} 1.0' in text
    assert 'device="skip0"' not in text


def test_format_prometheus_includes_network_errors():
    text = format_prometheus({"network": {"errin": 2, "errout": 0, "dropin": 4, "dropout": 1}})
    assert "# TYPE sysmon_network_errin counter" in text
    assert "sysmon_network_errin 2.0" in text
    assert "sysmon_network_dropin 4.0" in text


def test_format_prometheus_exports_byte_counters():
    text = format_prometheus(
        {
            "network": {"bytes_sent": 10.0, "bytes_recv": 20.0, "speed_up": 1.0, "speed_down": 2.0},
            "disk": {"percent": 1.0, "read_bytes": 30.0, "write_bytes": 40.0},
        }
    )
    assert "# TYPE sysmon_network_bytes_sent counter" in text
    assert "sysmon_network_bytes_sent 10.0" in text
    assert "sysmon_network_bytes_recv 20.0" in text
    assert "# TYPE sysmon_disk_read_bytes counter" in text
    assert "sysmon_disk_write_bytes 40.0" in text


def test_format_prometheus_includes_mount_inodes():
    text = format_prometheus(
        {
            "disk": {
                "percent": 10.0,
                "mounts": [
                    {"mount": "/", "percent": 10.0, "inode_percent": 20.0},
                    {"mount": "/data", "percent": None, "inode_percent": 30.0},
                ],
            }
        }
    )
    assert 'sysmon_disk_mount_inode_percent{mount="/"} 20.0' in text
    assert 'sysmon_disk_mount_inode_percent{mount="/data"} 30.0' in text
    assert text.count("# TYPE sysmon_disk_mount_inode_percent gauge") == 1


def test_format_prometheus_includes_mount_filesystem_type():
    text = format_prometheus(
        {
            "disk": {
                "percent": 1.0,
                "mounts": [{"mount": "/data", "percent": 1.0, "fstype": "ext4"}],
            }
        }
    )
    assert 'sysmon_disk_mount_info{mount="/data",fstype="ext4"} 1.0' in text


def test_format_prometheus_includes_mount_bytes():
    text = format_prometheus(
        {
            "disk": {
                "percent": 50.0,
                "mounts": [{"mount": "/data", "percent": 50.0, "used": 5, "free": 5, "total": 10}],
            }
        }
    )
    assert 'sysmon_disk_mount_used_bytes{mount="/data"} 5.0' in text
    assert 'sysmon_disk_mount_free_bytes{mount="/data"} 5.0' in text
    assert 'sysmon_disk_mount_total_bytes{mount="/data"} 10.0' in text


def test_format_prometheus_includes_disk_bytes():
    text = format_prometheus({"disk": {"percent": 25.0, "used": 25, "free": 75, "total": 100}})
    assert "sysmon_disk_used_bytes 25.0" in text
    assert "sysmon_disk_free_bytes 75.0" in text
    assert "sysmon_disk_total_bytes 100.0" in text


def test_format_prometheus_includes_inode_percent():
    text = format_prometheus({"disk": {"percent": 10.0, "inode_percent": 75.0}})
    assert "sysmon_disk_inode_percent 75.0" in text


def test_format_prometheus_includes_disk_speeds():
    text = format_prometheus(
        {"disk": {"percent": 10.0, "read_speed": 4096.0, "write_speed": 0.0}}
    )
    assert "sysmon_disk_read_speed 4096.0" in text
    assert "sysmon_disk_write_speed 0.0" in text


def test_format_prometheus_includes_memory_bytes():
    text = format_prometheus(
        {"memory": {"percent": 40.0, "used": 100.0, "available": 150.0, "total": 250.0}}
    )
    assert "sysmon_memory_used_bytes 100.0" in text
    assert "sysmon_memory_available_bytes 150.0" in text
    assert "sysmon_memory_total_bytes 250.0" in text


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


def test_format_prometheus_includes_battery_time_remaining():
    present = format_prometheus(
        {"sensors": {"battery": {"percent": 80.0, "power_plugged": False, "secsleft": 120}}}
    )
    assert "sysmon_battery_secsleft 120.0" in present
    absent = format_prometheus(
        {"sensors": {"battery": {"percent": 80.0, "power_plugged": True, "secsleft": None}}}
    )
    assert "sysmon_battery_secsleft" not in absent


def test_format_prometheus_includes_hottest_temperature():
    text = format_prometheus({"sensors": {"hottest_c": 61.0, "temperatures": {}}})
    assert "sysmon_temperature_hottest_celsius 61.0" in text


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
        assert response.getheader("Cache-Control") == "no-store"
        assert "sysmon_up 1.0" in body
        assert "sysmon_cpu_percent 12.5" in body
        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_server_head_has_headers_and_no_body():
    httpd = start_server("127.0.0.1", 0, payload_fn=lambda: _FAKE_ALL)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        port = httpd.server_address[1]
        conn = HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("HEAD", "/health")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200
        assert body == b""
        assert int(response.getheader("Content-Length")) > 0
        conn.request("HEAD", "/missing")
        missing = conn.getresponse()
        assert missing.status == 404
        assert missing.read() == b""
        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_server_accepts_trailing_slash():
    httpd = start_server("127.0.0.1", 0, payload_fn=lambda: _FAKE_ALL)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        port = httpd.server_address[1]
        conn = HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("GET", "/json/")
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["schema_version"] == 3
        conn.request("GET", "/metrics/")
        metrics = conn.getresponse()
        body = metrics.read().decode("utf-8")
        assert metrics.status == 200
        assert "sysmon_cpu_percent" in body
        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_server_payload_error_is_json_500():
    def boom() -> dict:
        raise RuntimeError("collect failed")

    httpd = start_server("127.0.0.1", 0, payload_fn=boom)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        port = httpd.server_address[1]
        conn = HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("GET", "/json")
        response = conn.getresponse()
        body = json.loads(response.read().decode("utf-8"))
        assert response.status == 500
        assert body["error"] == "collect failed"
        conn.request("GET", "/health")
        health = conn.getresponse()
        assert health.status == 200
        health.read()
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


def test_prime_rate_collectors_continues_when_one_sample_fails(monkeypatch):
    from sysmon.config import SysmonConfig
    from sysmon.server import _prime_rate_collectors

    def fake_collect(name, settings=None):
        if name == "network":
            raise RuntimeError("network down")
        return None

    monkeypatch.setattr("sysmon.collectors.registry.collect", fake_collect)
    monkeypatch.setattr("sysmon.server.time.sleep", lambda _seconds: None)
    _prime_rate_collectors(SysmonConfig(refresh_interval=2.0))


def test_prime_rate_collectors_skips_disabled_modules(monkeypatch):
    from sysmon.config import ModuleConfig, SysmonConfig
    from sysmon.server import _prime_rate_collectors

    names = []
    slept = []
    monkeypatch.setattr(
        "sysmon.collectors.registry.collect",
        lambda name, settings=None: names.append(name),
    )
    monkeypatch.setattr("sysmon.server.time.sleep", lambda seconds: slept.append(seconds))
    _prime_rate_collectors(
        SysmonConfig(
            modules=ModuleConfig(network=False, disk=False),
            refresh_interval=2.0,
        )
    )
    assert names == []
    assert slept == []


def test_serve_forever_primes_before_starting_service(monkeypatch):
    from sysmon.server import serve_forever

    order = []

    created = {}

    class FakeService:
        def __init__(self, **kwargs):
            created.update(kwargs)

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
    assert created["reload_config"] is True
    assert "serve" in order
    assert "stop" in order


def test_serve_forever_stops_collector_when_bind_fails(monkeypatch):
    import pytest

    from sysmon.server import serve_forever

    stopped = {"n": 0}

    class FakeService:
        def __init__(self, **_kwargs):
            return None

        def start(self):
            return None

        def stop(self):
            stopped["n"] += 1

        def get_snapshot(self):
            return {}

    monkeypatch.setattr("sysmon.server._prime_rate_collectors", lambda _settings: None)
    monkeypatch.setattr("sysmon.collectors.service.CollectorService", FakeService)

    def fail_bind(*_args, **_kwargs):
        raise OSError("address in use")

    monkeypatch.setattr("sysmon.server.start_server", fail_bind)
    with pytest.raises(SystemExit) as exc:
        serve_forever(host="127.0.0.1", port=9100)
    assert stopped["n"] == 1
    assert "address in use" in str(exc.value)
    assert "9100" in str(exc.value)
