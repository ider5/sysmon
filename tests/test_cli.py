"""End-to-end CLI tests via typer CliRunner."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from sysmon import __version__
from sysmon.cli import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"sysmon v{__version__}" in result.stdout


def test_snapshot_json(monkeypatch):
    monkeypatch.setattr("sysmon.cli._wait_for_rate_sampling", lambda _interval: None)
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


def test_snapshot_json_cpu_section(monkeypatch):
    monkeypatch.setattr("sysmon.cli._wait_for_rate_sampling", lambda _interval: None)
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
    monkeypatch.setattr("sysmon.cli._wait_for_rate_sampling", lambda _interval: None)
    result = runner.invoke(app, ["snapshot", "bogus", "--format", "json"])
    assert result.exit_code == 1
    assert "Unknown section" in result.stdout


def test_snapshot_unknown_format(monkeypatch):
    monkeypatch.setattr("sysmon.cli._wait_for_rate_sampling", lambda _interval: None)
    result = runner.invoke(app, ["snapshot", "--format", "yaml"])
    assert result.exit_code == 1
    assert "Unknown format" in result.stdout


def test_config_path():
    result = runner.invoke(app, ["config", "path"])
    assert result.exit_code == 0
    assert result.stdout.strip()
