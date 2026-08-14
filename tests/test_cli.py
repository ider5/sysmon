"""End-to-end CLI tests via typer CliRunner."""

from __future__ import annotations

import io
import json
import sys

from typer.testing import CliRunner

from sysmon import __version__
from sysmon.cli import app
from sysmon.config import DEFAULT_CONFIG

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"sysmon v{__version__}" in result.stdout


def test_snapshot_json(monkeypatch):
    monkeypatch.setattr("sysmon.cli._wait_for_rate_sampling", lambda *a, **k: None)
    result = runner.invoke(
        app,
        ["snapshot", "--format", "json", "--sample-interval", "0.1", "--no-gpu"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["schema_version"] == 3
    assert "cpu" in data
    assert "memory" in data
    assert "network" in data
    assert "disk" in data
    assert "gpu" not in data


def test_snapshot_loads_config_once(monkeypatch):
    calls = {"count": 0}

    def _counting_load_config():
        calls["count"] += 1
        return DEFAULT_CONFIG

    monkeypatch.setattr("sysmon.cli.load_config", _counting_load_config)
    monkeypatch.setattr("sysmon.cli._wait_for_rate_sampling", lambda *a, **k: None)
    monkeypatch.setattr(
        "sysmon.export.collect_all",
        lambda include_gpu=True: {"schema_version": 3, "cpu": {}},
    )
    result = runner.invoke(
        app,
        ["snapshot", "--format", "json", "--sample-interval", "0.1", "--no-gpu"],
    )
    assert result.exit_code == 0
    assert calls["count"] == 1


def test_snapshot_json_cpu_section(monkeypatch):
    monkeypatch.setattr("sysmon.cli._wait_for_rate_sampling", lambda *a, **k: None)
    result = runner.invoke(
        app,
        ["snapshot", "cpu", "--format", "json", "--sample-interval", "0.1"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "cpu" in data
    assert "percent" in data["cpu"]
    assert "status" in data["cpu"]


def test_snapshot_unknown_section(monkeypatch):
    monkeypatch.setattr("sysmon.cli._wait_for_rate_sampling", lambda *a, **k: None)
    result = runner.invoke(app, ["snapshot", "bogus", "--format", "json"])
    assert result.exit_code == 1
    assert "Unknown section" in result.stdout


def test_snapshot_unknown_format(monkeypatch):
    monkeypatch.setattr("sysmon.cli._wait_for_rate_sampling", lambda *a, **k: None)
    result = runner.invoke(app, ["snapshot", "--format", "yaml"])
    assert result.exit_code == 1
    assert "Unknown format" in result.stdout


def test_cpu_rich_uses_registry_collect(monkeypatch):
    calls = []

    def fake_collect(name, settings=None):
        calls.append(name)
        return {
            "percent": 1.0,
            "cores": [1.0, 2.0],
            "count_logical": 2,
            "count_physical": 1,
            "freq_current": 0,
            "freq_max": 0,
        }

    monkeypatch.setattr("sysmon.cli.load_config", lambda: DEFAULT_CONFIG)
    monkeypatch.setattr("sysmon.collectors.registry.collect", fake_collect)
    monkeypatch.setattr("sysmon.display.snapshot._print_cpu", lambda *a, **k: None)
    result = runner.invoke(app, ["cpu"])
    assert result.exit_code == 0
    assert "cpu" in calls


def test_wait_for_rate_sampling_uses_registry_collect(monkeypatch):
    calls = []
    monkeypatch.setattr("sysmon.cli.time.sleep", lambda _s: None)
    monkeypatch.setattr(
        "sysmon.collectors.registry.collect",
        lambda name, settings=None: calls.append(name),
    )
    from sysmon.cli import _wait_for_rate_sampling

    _wait_for_rate_sampling(0.1, DEFAULT_CONFIG)
    assert calls == ["network", "disk", "process"]


def test_top_json_uses_collect_processes(monkeypatch):
    captured = {}

    def fake_collect_processes(*_args, **kwargs):
        captured.update(kwargs)
        return [
            {
                "pid": 1,
                "name": "a",
                "cpu_percent": 1.0,
                "memory_percent": 1.0,
                "memory_mb": 1.0,
            }
        ]

    monkeypatch.setattr("sysmon.cli.load_config", lambda: DEFAULT_CONFIG)
    monkeypatch.setattr(
        "sysmon.collectors.registry.collect_processes", fake_collect_processes
    )
    result = runner.invoke(
        app, ["top", "--format", "json", "--limit", "3", "--sort", "memory"]
    )
    assert result.exit_code == 0
    assert captured["limit"] == 3
    assert captured["sort_by"] == "memory"


def test_cpu_json():
    result = runner.invoke(app, ["cpu", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "cpu" in data
    assert "percent" in data["cpu"]


def test_memory_json():
    result = runner.invoke(app, ["memory", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "memory" in data
    assert "percent" in data["memory"]


def test_top_json(monkeypatch):
    monkeypatch.setattr("sysmon.collectors.process.time.sleep", lambda _s: None)
    result = runner.invoke(app, ["top", "--format", "json", "--limit", "3"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "processes" in data
    assert data["sort_by"] == "cpu"
    assert isinstance(data["processes"], list)


def test_brief_passes_config_thresholds(monkeypatch):
    captured = {}

    monkeypatch.setattr("sysmon.cli.load_config", lambda: DEFAULT_CONFIG)

    def fake_print_brief(*args, **kwargs):
        captured["kwargs"] = kwargs

    monkeypatch.setattr("sysmon.display.brief.print_brief", fake_print_brief)
    result = runner.invoke(app, ["brief", "--no-gpu"])
    assert result.exit_code == 0
    assert captured["kwargs"]["thresholds"] is DEFAULT_CONFIG.thresholds


def test_brief_watch_passes_config_thresholds(monkeypatch):
    captured = {}

    monkeypatch.setattr("sysmon.cli.load_config", lambda: DEFAULT_CONFIG)

    def fake_watch(*args, **kwargs):
        captured["kwargs"] = kwargs

    monkeypatch.setattr("sysmon.display.brief.run_brief_watch", fake_watch)
    result = runner.invoke(app, ["brief", "--watch", "--no-gpu"])
    assert result.exit_code == 0
    assert captured["kwargs"]["thresholds"] is DEFAULT_CONFIG.thresholds


def test_brief_json(monkeypatch):
    monkeypatch.setattr("sysmon.cli.time.sleep", lambda _s: None)
    result = runner.invoke(app, ["brief", "--format", "json", "--no-gpu"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert set(data.keys()) == {"cpu", "memory", "network"}


def test_network_json(monkeypatch):
    monkeypatch.setattr("sysmon.cli.time.sleep", lambda _s: None)
    result = runner.invoke(
        app, ["network", "--format", "json", "--sample-interval", "0.1"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "network" in data
    assert "bytes_sent" in data["network"]


def test_disk_json(monkeypatch):
    monkeypatch.setattr("sysmon.cli.time.sleep", lambda _s: None)
    result = runner.invoke(
        app, ["disk", "--format", "json", "--sample-interval", "0.1"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "disk" in data
    assert "percent" in data["disk"]


def test_gpu_json():
    result = runner.invoke(app, ["gpu", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "gpu" in data


def test_snapshot_process_json(monkeypatch):
    monkeypatch.setattr("sysmon.cli._wait_for_rate_sampling", lambda *a, **k: None)
    result = runner.invoke(
        app,
        ["snapshot", "process", "--format", "json", "--sample-interval", "0.1"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "processes" in data
    assert isinstance(data["processes"], list)


def test_top_watch_rejects_json():
    result = runner.invoke(app, ["top", "--watch", "--format", "json"])
    assert result.exit_code == 1
    assert "JSON output is not supported with --watch" in result.stdout


def test_brief_watch_rejects_json():
    result = runner.invoke(app, ["brief", "--watch", "--format", "json"])
    assert result.exit_code == 1
    assert "JSON output is not supported with --title or --watch" in result.stdout


def test_config_init(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("sysmon.cli.get_config_path", lambda: config_path)
    monkeypatch.setattr("sysmon.paths.get_config_path", lambda: config_path)

    result = runner.invoke(app, ["config", "init"])
    assert result.exit_code == 0
    assert config_path.exists()

    again = runner.invoke(app, ["config", "init"])
    assert again.exit_code == 1
    assert "already exists" in again.stdout

    forced = runner.invoke(app, ["config", "init", "--force"])
    assert forced.exit_code == 0


def test_config_path():
    result = runner.invoke(app, ["config", "path"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_bare_sysmon_launches_dashboard(monkeypatch):
    called = {}

    def fake_run_dashboard(**kwargs):
        called["kwargs"] = kwargs

    monkeypatch.setattr("sysmon.display.dashboard.run_dashboard", fake_run_dashboard)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "kwargs" in called


def test_help_does_not_launch_dashboard(monkeypatch):
    monkeypatch.setattr(
        "sysmon.display.dashboard.run_dashboard",
        lambda **k: (_ for _ in ()).throw(AssertionError("dashboard launched")),
    )
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "dashboard" in result.stdout.lower()


def test_top_rejects_unknown_sort():
    result = runner.invoke(app, ["top", "--sort", "disk", "--format", "json"])
    assert result.exit_code == 1
    assert "Unknown sort key" in result.stdout


def test_gpu_json_disabled_by_flag():
    result = runner.invoke(app, ["gpu", "--format", "json", "--no-gpu"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data == {"gpu": None}


def test_serve_command_binds_localhost(monkeypatch):
    captured = {}

    def fake_serve(host="127.0.0.1", port=9100, allow_remote=False):
        captured["host"] = host
        captured["port"] = port
        captured["allow_remote"] = allow_remote

    monkeypatch.setattr("sysmon.server.serve_forever", fake_serve)
    result = runner.invoke(app, ["serve", "--port", "9101"])
    assert result.exit_code == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9101
    assert captured["allow_remote"] is False


def test_serve_rejects_non_loopback_without_allow_remote():
    result = runner.invoke(app, ["serve", "--host", "0.0.0.0"])
    assert result.exit_code == 1
    assert "allow-remote" in result.stdout.lower()


def test_configure_stdio_allows_emoji_on_cp1252_stdout(monkeypatch):
    buf = io.BytesIO()
    stream = io.TextIOWrapper(buf, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    from sysmon.cli import _configure_stdio

    _configure_stdio()
    sys.stdout.write("📊 CPU")
    sys.stdout.flush()
