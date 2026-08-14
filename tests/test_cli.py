"""End-to-end CLI tests via typer CliRunner."""

from __future__ import annotations

import json

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
