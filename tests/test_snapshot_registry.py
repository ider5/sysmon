"""Snapshot and live top collect through the registry."""

from __future__ import annotations

import io

from rich.console import Console

from sysmon.config import ModuleConfig, SysmonConfig, ThresholdConfig
from sysmon.display import snapshot as snapshot_mod
from sysmon.display import top_live as top_live_mod


def test_print_network_shows_packet_counts():
    info = {
        "speed_up": 0,
        "speed_down": 0,
        "bytes_sent": 10,
        "bytes_recv": 20,
        "packets_sent": 3,
        "packets_recv": 4,
    }
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, width=80)
    snapshot_mod._print_network(console, info)
    rendered = buffer.getvalue()
    assert "Packets" in rendered
    assert "3" in rendered
    assert "4" in rendered


def test_print_memory_shows_available():
    info = {
        "percent": 50.0,
        "used": 8 * 1024 ** 3,
        "total": 16 * 1024 ** 3,
        "available": 7 * 1024 ** 3,
        "swap_total": 0,
        "swap_used": 0,
        "swap_percent": 0.0,
    }
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, width=80)
    snapshot_mod._print_memory(console, info)
    assert "Available" in buffer.getvalue()


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


def test_print_snapshot_all_includes_sensors_when_enabled(monkeypatch):
    calls = []
    payload = {
        "battery": {"percent": 41.0, "secsleft": 90, "power_plugged": True},
        "temperatures": {},
    }

    def fake_collect(name, settings=None):
        calls.append(name)
        if name == "sensors":
            return payload
        raise AssertionError(name)

    monkeypatch.setattr(snapshot_mod, "collect", fake_collect)
    monkeypatch.setattr(
        snapshot_mod,
        "load_config",
        lambda: SysmonConfig(
            modules=ModuleConfig(
                cpu=False,
                memory=False,
                network=False,
                disk=False,
                gpu=False,
                process=False,
                sensors=True,
            )
        ),
    )
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, width=80)
    snapshot_mod.print_snapshot(console, section="all", include_gpu=False)
    rendered = buffer.getvalue()
    assert calls == ["sensors"]
    assert "41.0%" in rendered
    assert "plugged in" in rendered


def test_print_snapshot_sensors_section(monkeypatch):
    payload = {
        "battery": {"percent": 41.0, "secsleft": None, "power_plugged": False},
        "temperatures": {},
    }
    monkeypatch.setattr(snapshot_mod, "collect", lambda name, settings=None: payload)
    monkeypatch.setattr(snapshot_mod, "load_config", lambda: SysmonConfig())
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, width=80)
    snapshot_mod.print_snapshot(console, section="sensors")
    text = buffer.getvalue()
    assert "41.0%" in text
    assert "on battery" in text


def test_top_filter_accepts_command_keys():
    state = top_live_mod._TopState("memory", None)
    assert top_live_mod._apply_top_key(state, "/") is True
    assert state.filter_mode is True
    for key in ("c", "m", "q", "/"):
        assert top_live_mod._apply_top_key(state, key) is True
    assert state.sort_by == "memory"
    assert top_live_mod._apply_top_key(state, "\r") is True
    assert state.filter_mode is False
    assert state.name_filter == "cmq/"
    assert top_live_mod._apply_top_key(state, "q") is False


def test_top_commands_apply_outside_filter_mode():
    state = top_live_mod._TopState("memory", "chrome")
    assert top_live_mod._apply_top_key(state, "c") is True
    assert state.sort_by == "cpu"
    assert top_live_mod._apply_top_key(state, "\x1b") is True
    assert state.name_filter is None


def test_top_live_survives_a_bad_refresh(monkeypatch):
    calls = {"n": 0}
    updates = []

    def fake_collect_processes(**_kwargs):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("bad top")
        return []

    class FakeLive:
        def __init__(self, renderable, *a, **k):
            self.renderable = renderable

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def update(self, renderable):
            updates.append(renderable)

    monkeypatch.setattr(top_live_mod, "collect_processes", fake_collect_processes)
    monkeypatch.setattr(top_live_mod, "Live", FakeLive)
    monkeypatch.setattr(top_live_mod, "_read_key", lambda: None)
    monkeypatch.setattr(top_live_mod.time, "sleep", lambda _s: (_ for _ in ()).throw(KeyboardInterrupt()))
    top_live_mod.run_top_live(limit=3)
    assert calls["n"] >= 2
    assert any(getattr(item, "plain", "") == "top error: bad top" for item in updates)


def test_refresh_wait_quits_when_q_arrives(monkeypatch):
    state = top_live_mod._TopState("cpu", None)
    keys = iter([None, "q"])
    clock = {"t": 0.0}
    monkeypatch.setattr(top_live_mod, "_read_key", lambda: next(keys))
    monkeypatch.setattr(top_live_mod.time, "monotonic", lambda: clock["t"])

    def fake_sleep(seconds: float) -> None:
        clock["t"] += seconds

    monkeypatch.setattr(top_live_mod.time, "sleep", fake_sleep)
    assert top_live_mod._sleep_until_key_or_refresh(1.0, state) is False
    assert clock["t"] < 1.0


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
