"""Snapshot and live top collect through the registry."""

from __future__ import annotations

from rich.console import Console

from sysmon.config import SysmonConfig, ThresholdConfig
from sysmon.display import snapshot as snapshot_mod
from sysmon.display import top_live as top_live_mod


def test_print_snapshot_cpu_uses_registry_collect(monkeypatch):
    calls = []

    def fake_collect(name, settings=None):
        calls.append(name)
        if name == "cpu":
            return {
                "percent": 1.0,
                "cores": [1.0],
                "count_logical": 1,
                "count_physical": 1,
                "freq_current": 0,
                "freq_max": 0,
            }
        raise AssertionError(f"unexpected collector {name}")

    monkeypatch.setattr("sysmon.collectors.registry.collect", fake_collect)
    monkeypatch.setattr(snapshot_mod, "collect", fake_collect)
    monkeypatch.setattr(
        snapshot_mod,
        "load_config",
        lambda: SysmonConfig(thresholds=ThresholdConfig()),
    )
    snapshot_mod._print_cpu(Console(record=True))
    assert calls == ["cpu"]


def test_print_snapshot_all_uses_registry_collect(monkeypatch):
    calls = []

    def fake_collect(name, settings=None):
        calls.append(name)
        if name == "cpu":
            return {
                "percent": 1.0,
                "cores": [1.0],
                "count_logical": 1,
                "count_physical": 1,
                "freq_current": 0,
                "freq_max": 0,
            }
        if name == "memory":
            return {
                "total": 1,
                "used": 1,
                "available": 1,
                "percent": 1.0,
                "swap_total": 0,
                "swap_used": 0,
                "swap_percent": 0,
            }
        if name == "network":
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "speed_up": 0,
                "speed_down": 0,
                "packets_sent": 0,
                "packets_recv": 0,
            }
        if name == "disk":
            return {
                "mounts": [],
                "mount": "/",
                "total": 1,
                "used": 1,
                "free": 0,
                "percent": 1.0,
                "read_bytes": 0,
                "write_bytes": 0,
                "read_speed": 0,
                "write_speed": 0,
            }
        if name == "gpu":
            return None
        if name == "process":
            return []
        raise AssertionError(name)

    monkeypatch.setattr(snapshot_mod, "collect", fake_collect)
    monkeypatch.setattr(snapshot_mod, "load_config", lambda: SysmonConfig())
    snapshot_mod.print_snapshot(Console(record=True), section="all", include_gpu=True)
    assert calls == ["cpu", "memory", "network", "disk", "gpu", "process"]


def test_top_live_render_uses_collect_processes(monkeypatch):
    calls = []

    def fake_collect_processes(**kwargs):
        calls.append(kwargs)
        return []

    class FakeLive:
        def __init__(self, renderable, *a, **k):
            self.renderable = renderable

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def update(self, renderable):
            self.renderable = renderable

    monkeypatch.setattr(top_live_mod, "collect_processes", fake_collect_processes)
    monkeypatch.setattr(top_live_mod, "Live", FakeLive)
    monkeypatch.setattr(top_live_mod, "_read_key", lambda: "q")
    monkeypatch.setattr(top_live_mod.time, "sleep", lambda _s: None)

    top_live_mod.run_top_live(limit=3, sort_by="memory", name_filter="py")
    assert calls
    assert calls[0]["limit"] == 3
    assert calls[0]["sort_by"] == "memory"
    assert calls[0]["name_filter"] == "py"
