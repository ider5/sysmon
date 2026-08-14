"""Local HTTP server for JSON snapshots and Prometheus metrics."""

from __future__ import annotations

from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from sysmon.export import collect_all, collect_all_from_snapshot, to_json

PayloadFn = Callable[[], dict[str, Any]]
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _fmt(value: float) -> str:
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    if "." not in text:
        text += ".0"
    return text


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def format_prometheus(data: dict[str, Any]) -> str:
    """Render a Prometheus text exposition from a collect_all payload."""
    lines: list[str] = []

    def gauge(name: str, value: float, help_text: str) -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {_fmt(value)}")

    cpu = data.get("cpu")
    if isinstance(cpu, dict) and "percent" in cpu:
        gauge("sysmon_cpu_percent", cpu["percent"], "CPU utilization percent")
    memory = data.get("memory")
    if isinstance(memory, dict) and "percent" in memory:
        gauge("sysmon_memory_percent", memory["percent"], "Memory utilization percent")
    disk = data.get("disk")
    if isinstance(disk, dict) and "percent" in disk:
        gauge("sysmon_disk_percent", disk["percent"], "Primary disk utilization percent")
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
    gpus = data.get("gpu")
    samples: list[tuple[str, float]] = []
    if isinstance(gpus, list):
        for gpu in gpus:
            if isinstance(gpu, dict) and "load" in gpu:
                samples.append((str(gpu.get("id", 0)), float(gpu["load"])))
    if samples:
        lines.append("# HELP sysmon_gpu_load GPU utilization percent")
        lines.append("# TYPE sysmon_gpu_load gauge")
        for gpu_id, load in samples:
            lines.append(f'sysmon_gpu_load{{id="{_escape_label(gpu_id)}"}} {_fmt(load)}')
    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    """Serve /json and /metrics from a payload callback."""

    payload_fn: PayloadFn = staticmethod(collect_all)  # type: ignore[assignment]

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/json":
            body = to_json(self.payload_fn()).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)
            return
        if path == "/metrics":
            body = format_prometheus(self.payload_fn()).encode("utf-8")
            self._send(200, "text/plain; version=0.0.4; charset=utf-8", body)
            return
        if path in ("/", "/health"):
            self._send(
                200,
                "text/plain; charset=utf-8",
                b"sysmon serve\nGET /json\nGET /metrics\n",
            )
            return
        self._send(404, "text/plain; charset=utf-8", b"not found\n")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
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

    return ThreadingHTTPServer((host, port), BoundHandler)


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
    service = CollectorService(
        interval=settings.refresh_interval,
        include_gpu=settings.enable_gpu and settings.modules.gpu,
        config=settings,
    )
    service.start()

    def payload() -> dict[str, Any]:
        return collect_all_from_snapshot(service.get_snapshot(), settings=settings)

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
