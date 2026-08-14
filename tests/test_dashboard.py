"""Tests for dashboard layout building."""

from rich.console import Console

from sysmon.config import SysmonConfig
from sysmon.display.dashboard import build_dashboard


def _cpu_only_config() -> SysmonConfig:
    return SysmonConfig.from_mapping(
        {
            "modules": {
                "cpu": True,
                "memory": False,
                "network": False,
                "disk": False,
                "gpu": False,
                "process": False,
            }
        }
    )


def test_build_dashboard_placeholder_when_snapshot_missing(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("collector should not run on the UI thread")

    monkeypatch.setattr("sysmon.collectors.cpu.get_cpu_snapshot", boom)
    layout = build_dashboard(
        include_gpu=False,
        config=_cpu_only_config(),
        snapshot={},
    )
    console = Console(record=True, width=80)
    console.print(layout)
    assert "Waiting for metrics" in console.export_text()


def test_build_dashboard_uses_snapshot_cpu(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("collector should not run when snapshot has data")

    monkeypatch.setattr("sysmon.collectors.cpu.get_cpu_snapshot", boom)
    snapshot = {
        "cpu": {
            "percent": 12.5,
            "cores": [12.5],
            "count_logical": 1,
            "count_physical": 1,
            "freq_current": 1000,
            "freq_max": 2000,
        }
    }
    layout = build_dashboard(
        include_gpu=False,
        config=_cpu_only_config(),
        snapshot=snapshot,
    )
    console = Console(record=True, width=100)
    console.print(layout)
    assert "12.5%" in console.export_text()


def test_build_dashboard_gpu_none_is_unavailable(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("collector should not run")

    monkeypatch.setattr("sysmon.collectors.gpu.get_gpu_info", boom)
    config = SysmonConfig.from_mapping(
        {
            "modules": {
                "cpu": False,
                "memory": False,
                "network": False,
                "disk": False,
                "gpu": True,
                "process": False,
            }
        }
    )
    layout = build_dashboard(include_gpu=True, config=config, snapshot={"gpu": None})
    console = Console(record=True, width=80)
    console.print(layout)
    text = console.export_text()
    assert "No GPU" in text
    assert "Waiting for metrics" not in text


def test_build_dashboard_shows_collector_error(monkeypatch):
    config = SysmonConfig.from_mapping(
        {
            "modules": {
                "cpu": True,
                "memory": False,
                "network": False,
                "disk": False,
                "gpu": False,
                "process": False,
            }
        }
    )
    layout = build_dashboard(
        include_gpu=False,
        config=config,
        snapshot={"errors": {"cpu": "cpu down"}},
    )
    console = Console(record=True, width=80)
    console.print(layout)
    assert "Collection error: cpu down" in console.export_text()
