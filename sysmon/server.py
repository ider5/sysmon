"""Local HTTP server for JSON snapshots and Prometheus metrics."""

from __future__ import annotations

import math
import socket
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from sysmon.config import SysmonConfig
from sysmon.export import collect_all, collect_all_from_snapshot, to_json

PayloadFn = Callable[[], dict[str, Any]]
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_RATE_PRIME_SLEEP = 0.5


def _is_ipv6_host(host: str) -> bool:
    try:
        socket.inet_pton(socket.AF_INET6, host)
        return True
    except OSError:
        return False


def _http_server_class(host: str) -> type[ThreadingHTTPServer]:
    if not _is_ipv6_host(host):
        return ThreadingHTTPServer

    class IPv6ThreadingHTTPServer(ThreadingHTTPServer):
        address_family = socket.AF_INET6

    return IPv6ThreadingHTTPServer


def _prime_rate_collectors(settings: SysmonConfig) -> None:
    """Take a first network/disk sample so the next collect has speeds."""
    from sysmon.collectors.registry import collect

    primed = False
    if settings.modules.network:
        collect("network", settings)
        primed = True
    if settings.modules.disk:
        collect("disk", settings)
        primed = True
    if primed:
        time.sleep(min(_RATE_PRIME_SLEEP, settings.refresh_interval))


def _fmt(value: float) -> str:
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    if "." not in text:
        text += ".0"
    return text


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _first_number(payload: dict, *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        return float(value)
    return None


def _labeled_gauge(
    lines: list[str],
    name: str,
    help_text: str,
    label: str,
    samples: list[tuple[str, float]],
) -> None:
    emitted = [
        (label_value, value)
        for label_value, value in samples
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    ]
    if not emitted:
        return
    lines.append(f"# HELP {name} {help_text}")
    lines.append(f"# TYPE {name} gauge")
    for label_value, value in emitted:
        lines.append(f'{name}{{{label}="{_escape_label(label_value)}"}} {_fmt(value)}')


def format_prometheus(data: dict[str, Any]) -> str:
    """Render a Prometheus text exposition from a collect_all payload."""
    lines: list[str] = []

    def _emit(name: str, value: object, help_text: str, metric_type: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return
        if not math.isfinite(float(value)):
            return
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {metric_type}")
        lines.append(f"{name} {_fmt(float(value))}")

    def gauge(name: str, value: float, help_text: str) -> None:
        _emit(name, value, help_text, "gauge")

    def counter(name: str, value: float, help_text: str) -> None:
        _emit(name, value, help_text, "counter")

    gauge("sysmon_up", 1, "1 when the sysmon metrics endpoint is serving")
    uptime_seconds = _first_number(data, "uptime_seconds")
    if uptime_seconds is not None:
        gauge("sysmon_uptime_seconds", uptime_seconds, "Time since boot in seconds")
    errors = data.get("errors")
    if isinstance(errors, dict) and errors:
        gauge(
            "sysmon_section_errors",
            len(errors),
            "Number of sections that failed while building this sample",
        )
    collected_at = _first_number(data, "collected_at")
    if collected_at is not None:
        gauge(
            "sysmon_collected_at_seconds",
            collected_at,
            "Unix time when this sample was taken",
        )
        gauge(
            "sysmon_sample_age_seconds",
            max(0.0, time.time() - collected_at),
            "Seconds since this sample was taken",
        )
    cpu = data.get("cpu")
    if isinstance(cpu, dict) and "percent" in cpu:
        gauge("sysmon_cpu_percent", cpu["percent"], "CPU utilization percent")
        logical = _first_number(cpu, "count_logical")
        physical = _first_number(cpu, "count_physical")
        if logical is not None:
            gauge("sysmon_cpu_logical", logical, "Logical CPU count")
        if physical is not None:
            gauge("sysmon_cpu_physical", physical, "Physical CPU count")
        load_avg = cpu.get("load_avg")
        if (
            isinstance(load_avg, (list, tuple))
            and len(load_avg) == 3
            and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in load_avg)
        ):
            lines.append("# HELP sysmon_load_average Load average by window")
            lines.append("# TYPE sysmon_load_average gauge")
            for window, value in zip(("1m", "5m", "15m"), load_avg):
                lines.append(f'sysmon_load_average{{window="{window}"}} {_fmt(float(value))}')
    memory = data.get("memory")
    if isinstance(memory, dict) and isinstance(memory.get("percent"), (int, float)):
        if not isinstance(memory.get("percent"), bool):
            gauge("sysmon_memory_percent", memory["percent"], "Memory utilization percent")
        for key, metric, help_text in (
            ("used", "sysmon_memory_used_bytes", "Memory used in bytes"),
            ("available", "sysmon_memory_available_bytes", "Memory available in bytes"),
            ("total", "sysmon_memory_total_bytes", "Memory total in bytes"),
        ):
            value = _first_number(memory, key)
            if value is not None:
                gauge(metric, value, help_text)
        swap_total = memory.get("swap_total")
        swap_percent = memory.get("swap_percent")
        if (
            isinstance(swap_total, (int, float))
            and not isinstance(swap_total, bool)
            and swap_total > 0
            and isinstance(swap_percent, (int, float))
            and not isinstance(swap_percent, bool)
        ):
            gauge("sysmon_swap_percent", swap_percent, "Swap utilization percent")
            swap_used = memory.get("swap_used")
            if isinstance(swap_used, (int, float)) and not isinstance(swap_used, bool):
                gauge("sysmon_swap_used_bytes", swap_used, "Swap space used in bytes")
            gauge("sysmon_swap_total_bytes", swap_total, "Swap space total in bytes")
    disk = data.get("disk")
    if isinstance(disk, dict) and "percent" in disk:
        gauge("sysmon_disk_percent", disk["percent"], "Primary disk utilization percent")
        for key, metric, help_text in (
            ("used", "sysmon_disk_used_bytes", "Primary disk bytes used"),
            ("free", "sysmon_disk_free_bytes", "Primary disk bytes free"),
            ("total", "sysmon_disk_total_bytes", "Primary disk bytes total"),
        ):
            value = _first_number(disk, key)
            if value is not None:
                gauge(metric, value, help_text)
        inode_percent = _first_number(disk, "inode_percent")
        if inode_percent is not None:
            gauge(
                "sysmon_disk_inode_percent",
                inode_percent,
                "Primary disk inode utilization percent",
            )
        mount_samples: list[tuple[str, float]] = []
        inode_samples: list[tuple[str, float]] = []
        mounts = disk.get("mounts")
        if isinstance(mounts, list):
            for mount in mounts:
                if not isinstance(mount, dict):
                    continue
                name = str(mount.get("mount", ""))
                percent = _first_number(mount, "percent")
                inode = _first_number(mount, "inode_percent")
                if percent is not None:
                    mount_samples.append((name, percent))
                if inode is not None:
                    inode_samples.append((name, inode))
        if mount_samples:
            lines.append("# HELP sysmon_disk_mount_percent Disk utilization percent by mount")
            lines.append("# TYPE sysmon_disk_mount_percent gauge")
            for mount, percent in mount_samples:
                lines.append(
                    f'sysmon_disk_mount_percent{{mount="{_escape_label(mount)}"}} {_fmt(percent)}'
                )
        if inode_samples:
            lines.append(
                "# HELP sysmon_disk_mount_inode_percent Inode utilization percent by mount"
            )
            lines.append("# TYPE sysmon_disk_mount_inode_percent gauge")
            for mount, inode in inode_samples:
                lines.append(
                    "sysmon_disk_mount_inode_percent"
                    f'{{mount="{_escape_label(mount)}"}} {_fmt(inode)}'
                )
        read_speed = _first_number(disk, "read_speed")
        write_speed = _first_number(disk, "write_speed")
        if read_speed is not None:
            gauge(
                "sysmon_disk_read_speed",
                read_speed,
                "Disk read throughput in bytes per second",
            )
        if write_speed is not None:
            gauge(
                "sysmon_disk_write_speed",
                write_speed,
                "Disk write throughput in bytes per second",
            )
        read_bytes = _first_number(disk, "read_bytes")
        write_bytes = _first_number(disk, "write_bytes")
        if read_bytes is not None:
            counter("sysmon_disk_read_bytes", read_bytes, "Bytes read since boot")
        if write_bytes is not None:
            counter("sysmon_disk_write_bytes", write_bytes, "Bytes written since boot")
    network = data.get("network")
    if isinstance(network, dict):
        if "speed_up" in network:
            gauge(
                "sysmon_network_speed_up",
                network["speed_up"],
                "Upload throughput in bytes per second",
            )
        if "speed_down" in network:
            gauge(
                "sysmon_network_speed_down",
                network["speed_down"],
                "Download throughput in bytes per second",
            )
        sent = _first_number(network, "bytes_sent")
        recv = _first_number(network, "bytes_recv")
        if sent is not None:
            counter("sysmon_network_bytes_sent", sent, "Bytes sent since boot")
        if recv is not None:
            counter("sysmon_network_bytes_recv", recv, "Bytes received since boot")
        for key, metric, help_text in (
            ("errin", "sysmon_network_errin", "Inbound packets with errors"),
            ("errout", "sysmon_network_errout", "Outbound packets with errors"),
            ("dropin", "sysmon_network_dropin", "Inbound packets dropped"),
            ("dropout", "sysmon_network_dropout", "Outbound packets dropped"),
        ):
            value = _first_number(network, key)
            if value is not None:
                counter(metric, value, help_text)
        up_samples: list[tuple[str, float]] = []
        down_samples: list[tuple[str, float]] = []
        interfaces = network.get("interfaces")
        if isinstance(interfaces, list):
            for iface in interfaces:
                if not isinstance(iface, dict):
                    continue
                name = str(iface.get("name", ""))
                if isinstance(iface.get("speed_up"), (int, float)):
                    up_samples.append((name, float(iface["speed_up"])))
                if isinstance(iface.get("speed_down"), (int, float)):
                    down_samples.append((name, float(iface["speed_down"])))
        if up_samples:
            lines.append(
                "# HELP sysmon_network_interface_speed_up "
                "Per-interface upload throughput in bytes per second"
            )
            lines.append("# TYPE sysmon_network_interface_speed_up gauge")
            for name, speed in up_samples:
                lines.append(
                    "sysmon_network_interface_speed_up"
                    f'{{device="{_escape_label(name)}"}} {_fmt(speed)}'
                )
        if down_samples:
            lines.append(
                "# HELP sysmon_network_interface_speed_down "
                "Per-interface download throughput in bytes per second"
            )
            lines.append("# TYPE sysmon_network_interface_speed_down gauge")
            for name, speed in down_samples:
                lines.append(
                    "sysmon_network_interface_speed_down"
                    f'{{device="{_escape_label(name)}"}} {_fmt(speed)}'
                )
    gpus = data.get("gpu")
    samples: list[tuple[str, float]] = []
    memory_used: list[tuple[str, float]] = []
    memory_total: list[tuple[str, float]] = []
    gpu_temps: list[tuple[str, float]] = []
    if isinstance(gpus, list):
        for gpu in gpus:
            if not isinstance(gpu, dict):
                continue
            gpu_id = str(gpu.get("id", 0))
            if isinstance(gpu.get("load"), (int, float)) and not isinstance(gpu.get("load"), bool):
                samples.append((gpu_id, float(gpu["load"])))
            used = _first_number(gpu, "memory_used_mb", "memory_used")
            total = _first_number(gpu, "memory_total_mb", "memory_total")
            temp = _first_number(gpu, "temperature_c", "temperature")
            if used is not None:
                memory_used.append((gpu_id, used))
            if total is not None:
                memory_total.append((gpu_id, total))
            if temp is not None:
                gpu_temps.append((gpu_id, temp))
    _labeled_gauge(
        lines,
        "sysmon_gpu_load",
        "GPU utilization percent",
        "id",
        samples,
    )
    _labeled_gauge(
        lines,
        "sysmon_gpu_memory_used_mb",
        "GPU memory used in megabytes",
        "id",
        memory_used,
    )
    _labeled_gauge(
        lines,
        "sysmon_gpu_memory_total_mb",
        "GPU memory total in megabytes",
        "id",
        memory_total,
    )
    _labeled_gauge(
        lines,
        "sysmon_gpu_temperature_celsius",
        "GPU temperature in Celsius",
        "id",
        gpu_temps,
    )

    sensors = data.get("sensors")
    if isinstance(sensors, dict):
        battery = sensors.get("battery")
        if isinstance(battery, dict) and isinstance(battery.get("percent"), (int, float)):
            gauge(
                "sysmon_battery_percent",
                battery["percent"],
                "Battery charge percent",
            )
            gauge(
                "sysmon_battery_plugged",
                1.0 if battery.get("power_plugged") else 0.0,
                "1 when external power is connected",
            )
            secsleft = _first_number(battery, "secsleft")
            if secsleft is not None and secsleft >= 0:
                gauge(
                    "sysmon_battery_secsleft",
                    secsleft,
                    "Seconds of battery remaining",
                )
        temperatures = sensors.get("temperatures")
        temp_samples: list[tuple[str, str, float]] = []
        if isinstance(temperatures, dict):
            for group, entries in temperatures.items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    current = entry.get("current")
                    if not isinstance(current, (int, float)):
                        continue
                    temp_samples.append(
                        (str(group), str(entry.get("label") or ""), float(current))
                    )
        if temp_samples:
            lines.append("# HELP sysmon_temperature_celsius Sensor temperature in Celsius")
            lines.append("# TYPE sysmon_temperature_celsius gauge")
            for group, label, current in temp_samples:
                lines.append(
                    "sysmon_temperature_celsius"
                    f'{{sensor="{_escape_label(group)}",label="{_escape_label(label)}"}} '
                    f"{_fmt(current)}"
                )
    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    """Serve /json and /metrics from a payload callback."""

    payload_fn: PayloadFn = staticmethod(collect_all)  # type: ignore[assignment]

    def do_GET(self) -> None:  # noqa: N802
        self._handle(include_body=True)

    def do_HEAD(self) -> None:  # noqa: N802
        self._handle(include_body=False)

    def _handle(self, include_body: bool) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path == "/json":
                body = to_json(self.payload_fn()).encode("utf-8")
                self._send(200, "application/json; charset=utf-8", body, include_body)
                return
            if path == "/metrics":
                body = format_prometheus(self.payload_fn()).encode("utf-8")
                self._send(
                    200,
                    "text/plain; version=0.0.4; charset=utf-8",
                    body,
                    include_body,
                )
                return
            if path in ("/", "/health"):
                self._send(
                    200,
                    "text/plain; charset=utf-8",
                    b"sysmon serve\nGET /json\nGET /metrics\n",
                    include_body,
                )
                return
            self._send(404, "text/plain; charset=utf-8", b"not found\n", include_body)
        except Exception as exc:
            body = to_json({"error": str(exc)}).encode("utf-8")
            self._send(500, "application/json; charset=utf-8", body, include_body)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(
        self,
        status: int,
        content_type: str,
        body: bytes,
        include_body: bool = True,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if include_body:
            self.wfile.write(body)


def start_server(
    host: str,
    port: int,
    payload_fn: PayloadFn | None = None,
) -> ThreadingHTTPServer:
    """Bind a threaded HTTP server (port 0 selects an ephemeral port)."""
    fn = payload_fn or collect_all

    class BoundHandler(MetricsHandler):
        payload_fn = staticmethod(fn)  # type: ignore[assignment]

    return _http_server_class(host)((host, port), BoundHandler)


def serve_forever(
    host: str = "127.0.0.1",
    port: int = 9100,
    allow_remote: bool = False,
) -> None:
    """Serve JSON and Prometheus endpoints from CollectorService until interrupted."""
    if not allow_remote and host not in LOOPBACK_HOSTS:
        raise ValueError("non-loopback bind requires allow_remote=True")

    from sysmon.collectors.service import CollectorService
    from sysmon.config import load_config

    settings = load_config()
    _prime_rate_collectors(settings)
    service = CollectorService(
        interval=settings.refresh_interval,
        include_gpu=True,
        config=settings,
        reload_config=True,
    )
    service.start()

    def payload() -> dict[str, Any]:
        current = load_config()
        return collect_all_from_snapshot(
            service.get_snapshot(),
            include_gpu=current.enable_gpu and current.modules.gpu,
            settings=current,
        )

    httpd = start_server(host, port, payload_fn=payload)
    bound_host, bound_port = httpd.server_address[:2]
    print(f"sysmon serving on http://{bound_host}:{bound_port}/json")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        httpd.server_close()
        service.stop()
