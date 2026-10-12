"""Tests for dashboard layout building."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from sysmon.config import SysmonConfig
from sysmon.display.dashboard import build_dashboard, run_dashboard
from sysmon.display.sparkline import HistoryBuffer


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


def test_record_dashboard_history_skips_missing_numbers():
    from sysmon.display.dashboard import record_dashboard_history
    from sysmon.display.sparkline import HistoryBuffer

    cpu = HistoryBuffer()
    mem = HistoryBuffer()
    down = HistoryBuffer()
    up = HistoryBuffer()
    read = HistoryBuffer()
    write = HistoryBuffer()
    record_dashboard_history(
        {"cpu": {}, "memory": {"percent": 12.0}, "network": {"speed_down": True}, "disk": None},
        cpu,
        mem,
        down,
        up,
        read,
        write,
    )
    assert cpu.values() == []
    assert mem.values() == [12.0]
    assert down.values() == []
    assert read.values() == []


def test_snapshot_is_stale_after_several_refreshes():
    from sysmon.display.dashboard import snapshot_is_stale

    assert snapshot_is_stale({"timestamp": 100.0}, 1.0, now=110.0) is True
    assert snapshot_is_stale({"timestamp": 100.0}, 1.0, now=102.0) is False
    assert snapshot_is_stale({}, 1.0, now=200.0) is False
    assert snapshot_is_stale({"timestamp": float("inf")}, 1.0, now=110.0) is True
    assert snapshot_is_stale({"timestamp": float("nan")}, 1.0, now=110.0) is True


def test_build_dashboard_shows_stale_notice():
    layout = build_dashboard(
        include_gpu=False,
        config=_cpu_only_config(),
        snapshot={"timestamp": 1.0},
        notice="stale",
    )
    console = Console(record=True, width=120)
    console.print(layout)
    assert "stale" in console.export_text()


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


def test_build_dashboard_cpu_without_cores_still_draws():
    layout = build_dashboard(
        include_gpu=False,
        config=_cpu_only_config(),
        snapshot={"cpu": {"percent": 12.5, "count_logical": 2, "count_physical": 1}},
    )
    console = Console(record=True, width=100)
    console.print(layout)
    assert "12.5%" in console.export_text()


def test_build_dashboard_non_record_cpu_waits():
    layout = build_dashboard(
        include_gpu=False,
        config=_cpu_only_config(),
        snapshot={"cpu": "bad", "errors": {"cpu": "unavailable"}},
    )
    console = Console(record=True, width=100)
    console.print(layout)
    text = console.export_text()
    assert "unavailable" in text
    assert "Per-core" not in text


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


def test_build_dashboard_passes_gpu_thresholds(monkeypatch):
    captured = {}

    def fake_gpu_panel(gpus, warn=80.0, critical=95.0):
        captured["warn"] = warn
        captured["critical"] = critical
        captured["gpus"] = gpus
        from rich.panel import Panel
        from rich.text import Text

        return Panel(Text("gpu"))

    monkeypatch.setattr("sysmon.display.dashboard.gpu_panel", fake_gpu_panel)
    config = SysmonConfig.from_mapping(
        {
            "modules": {
                "cpu": False,
                "memory": False,
                "network": False,
                "disk": False,
                "gpu": True,
                "process": False,
            },
            "thresholds": {"gpu_warn": 12, "gpu_critical": 34},
        }
    )
    gpu = [
        {
            "id": 0,
            "name": "Fake",
            "load": 15.0,
            "memory_used": 1.0,
            "memory_total": 2.0,
            "temperature": 40.0,
        }
    ]
    build_dashboard(include_gpu=True, config=config, snapshot={"gpu": gpu})
    assert captured["warn"] == 12.0
    assert captured["critical"] == 34.0
    assert captured["gpus"] == gpu


def test_build_dashboard_process_row_is_full_width():
    config = SysmonConfig.from_mapping(
        {
            "modules": {
                "cpu": True,
                "memory": True,
                "network": False,
                "disk": False,
                "gpu": False,
                "process": True,
            }
        }
    )
    snapshot = {
        "cpu": {
            "percent": 12.5,
            "cores": [12.5],
            "count_logical": 1,
            "count_physical": 1,
            "freq_current": 1000,
            "freq_max": 2000,
        },
        "memory": {
            "percent": 10.0,
            "used": 1 * 1024 ** 3,
            "total": 2 * 1024 ** 3,
            "available": 1 * 1024 ** 3,
            "swap_total": 0,
            "swap_used": 0,
            "swap_percent": 0.0,
        },
        "process": [
            {
                "pid": 4242,
                "name": "python",
                "cpu_percent": 12.3,
                "memory_percent": 1.5,
                "memory_mb": 50.0,
            }
        ],
    }
    layout = build_dashboard(include_gpu=False, config=config, snapshot=snapshot)
    content = layout["content"]
    assert [child.name for child in content.children] == ["row0", "row1"]
    assert [child.name for child in content["row0"].children] == ["cpu", "memory"]
    assert content["row1"].children == []

    console = Console(record=True, width=120)
    console.print(layout)
    text = console.export_text()
    assert "4242" in text
    assert "python" in text
    assert "PID" in text


def test_build_dashboard_renders_memory_history():
    history = HistoryBuffer()
    history.add(10.0)
    history.add(90.0)
    config = SysmonConfig.from_mapping(
        {
            "modules": {
                "cpu": False,
                "memory": True,
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
        mem_history=history,
        snapshot={
            "memory": {
                "percent": 90.0,
                "used": 9 * 1024 ** 3,
                "total": 10 * 1024 ** 3,
                "available": 1 * 1024 ** 3,
                "swap_total": 0,
                "swap_used": 0,
                "swap_percent": 0.0,
            }
        },
    )
    console = Console(record=True, width=100)
    console.print(layout)
    assert "History" in console.export_text()


def _sensors_only_config() -> SysmonConfig:
    return SysmonConfig.from_mapping(
        {
            "modules": {
                "cpu": False,
                "memory": False,
                "network": False,
                "disk": False,
                "gpu": False,
                "process": False,
                "sensors": True,
            }
        }
    )


def test_build_dashboard_omits_sensors_when_module_disabled():
    layout = build_dashboard(
        include_gpu=False,
        config=_cpu_only_config(),
        snapshot={
            "sensors": {
                "battery": {"percent": 80.0, "secsleft": None, "power_plugged": True},
                "temperatures": {},
            }
        },
    )
    console = Console(record=True, width=80)
    console.print(layout)
    text = console.export_text()
    assert "Sensors" not in text
    assert "80.0%" not in text


def test_build_dashboard_shows_enabled_sensors():
    layout = build_dashboard(
        include_gpu=False,
        config=_sensors_only_config(),
        snapshot={
            "sensors": {
                "battery": {
                    "percent": 80.0,
                    "secsleft": 3700,
                    "power_plugged": False,
                },
                "temperatures": {
                    "coretemp": [
                        {
                            "label": "Package",
                            "current": 62.0,
                            "high": 80.0,
                            "critical": 100.0,
                        }
                    ]
                },
            }
        },
    )
    console = Console(record=True, width=80)
    console.print(layout)
    text = console.export_text()
    assert "Sensors" in text
    assert "80.0%" in text
    assert "on battery" in text
    assert "Package" in text
    assert "62.0°C" in text


def test_build_dashboard_sensors_waiting_and_error():
    waiting = build_dashboard(
        include_gpu=False,
        config=_sensors_only_config(),
        snapshot={},
    )
    console = Console(record=True, width=80)
    console.print(waiting)
    assert "Waiting for metrics" in console.export_text()

    failed = build_dashboard(
        include_gpu=False,
        config=_sensors_only_config(),
        snapshot={"errors": {"sensors": "sensor read failed"}},
    )
    console = Console(record=True, width=80)
    console.print(failed)
    assert "Collection error: sensor read failed" in console.export_text()


def test_run_dashboard_skips_rate_prime_when_modules_off(monkeypatch):
    calls: list[str] = []

    class FakeService:
        def __init__(self, **_kwargs):
            return None

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

        def get_snapshot(self) -> dict:
            return {}

    class FakeLive:
        def __init__(self, renderable, **kwargs):
            self.renderable = renderable

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def update(self, renderable) -> None:
            self.renderable = renderable

    def fake_sleep(_seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("sysmon.display.dashboard.CollectorService", FakeService)
    monkeypatch.setattr("sysmon.display.dashboard.Live", FakeLive)
    monkeypatch.setattr("sysmon.display.dashboard.time.sleep", fake_sleep)
    monkeypatch.setattr(
        "sysmon.collectors.registry.collect",
        lambda name, *_args, **_kwargs: calls.append(name),
    )
    monkeypatch.setattr("sysmon.display.dashboard.load_config", lambda: _cpu_only_config())

    run_dashboard(refresh_rate=1.0, include_gpu=False)
    assert calls == []


def test_run_dashboard_shows_display_error_and_continues(monkeypatch):
    builds = {"n": 0}

    def flaky_build(*_args, **_kwargs):
        builds["n"] += 1
        if builds["n"] > 1:
            raise RuntimeError("bad frame")
        return Panel(Text("ok"))

    sleeps = {"n": 0}

    def fake_sleep(_seconds: float) -> None:
        sleeps["n"] += 1
        if sleeps["n"] >= 2:
            raise KeyboardInterrupt

    class FakeService:
        def __init__(self, **_kwargs):
            return None

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

        def get_snapshot(self) -> dict:
            return {}

    class FakeLive:
        def __init__(self, renderable, **kwargs):
            self.renderable = renderable

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def update(self, renderable) -> None:
            self.frames.append(renderable)

        frames: list = []

    monkeypatch.setattr("sysmon.display.dashboard.CollectorService", FakeService)
    monkeypatch.setattr("sysmon.display.dashboard.Live", FakeLive)
    monkeypatch.setattr("sysmon.display.dashboard.time.sleep", fake_sleep)
    monkeypatch.setattr("sysmon.collectors.registry.collect", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "sysmon.display.dashboard.load_config", lambda: _sensors_only_config()
    )
    monkeypatch.setattr("sysmon.display.dashboard.build_dashboard", flaky_build)

    run_dashboard(refresh_rate=1.0, include_gpu=False)
    assert builds["n"] >= 2
    assert sleeps["n"] >= 2


def test_run_dashboard_follows_sensor_module_config(monkeypatch):
    captured = {}

    class FakeService:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

        def get_snapshot(self) -> dict:
            return {}

    sleeps = {"n": 0}

    def fake_sleep(_seconds: float) -> None:
        sleeps["n"] += 1
        if sleeps["n"] >= 2:
            raise KeyboardInterrupt

    class FakeLive:
        def __init__(self, renderable, **kwargs):
            self.renderable = renderable

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def update(self, renderable) -> None:
            self.renderable = renderable

    monkeypatch.setattr("sysmon.display.dashboard.CollectorService", FakeService)
    monkeypatch.setattr("sysmon.display.dashboard.Live", FakeLive)
    monkeypatch.setattr("sysmon.display.dashboard.time.sleep", fake_sleep)
    monkeypatch.setattr("sysmon.collectors.registry.collect", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "sysmon.display.dashboard.load_config", lambda: _sensors_only_config()
    )

    run_dashboard(refresh_rate=1.0, include_gpu=False)
    assert captured["include_sensors"] is None
    assert captured["include_gpu"] is False
    assert captured["reload_config"] is True
    assert captured["config"].modules.sensors is True
