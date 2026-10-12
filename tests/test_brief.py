"""Tests for brief mode helpers and title-mode startup."""

from __future__ import annotations

import subprocess

from rich.console import Console

from sysmon.config import ModuleConfig, SysmonConfig, ThresholdConfig
from sysmon.display import brief as brief_mod


def _span_styles_for(text, needle: str) -> list[str]:
    start = text.plain.index(needle)
    end = start + len(needle)
    return [
        str(span.style)
        for span in text.spans
        if span.start < end and span.end > start
    ]


def _stub_brief_collectors(
    monkeypatch,
    *,
    cpu_percent=1.0,
    memory_percent=50.0,
    gpu=None,
    network_interfaces=None,
):
    seen = {"interfaces": None}

    def fake_collect(name, settings=None):
        if name == "cpu":
            return {"percent": cpu_percent, "freq_current": 0, "cores": []}
        if name == "memory":
            return {"used": 1, "total": 2, "percent": memory_percent}
        if name == "disk":
            return {"percent": 10.0, "read_speed": 0, "write_speed": 0}
        if name == "network":
            if settings is not None:
                seen["interfaces"] = settings.network_interfaces
            return {
                "speed_up": 0,
                "speed_down": 0,
                "bytes_sent": 0,
                "bytes_recv": 0,
            }
        if name == "gpu":
            return gpu
        raise AssertionError(name)

    monkeypatch.setattr(brief_mod, "collect", fake_collect)
    monkeypatch.setattr(brief_mod, "bytes_to_gb", lambda n: 1.0)
    monkeypatch.setattr(brief_mod, "format_speed", lambda n: "0 B/s")
    return seen


class _AliveProc:
    pid = 4242

    def poll(self):
        return None


class _DeadProc:
    pid = 7

    def poll(self):
        return 1


def test_format_network_errors_only_when_nonzero():
    assert brief_mod._format_network_errors({"errin": 0, "errout": 0, "dropin": 0, "dropout": 0}) is None
    text = brief_mod._format_network_errors({"errin": 2, "dropin": 1})
    assert text is not None
    assert text.plain == "ERR 2/0 DROP 1/0"


def test_format_cpu_shows_load_when_it_meets_cpu_count():
    quiet = brief_mod._format_cpu(
        {"percent": 10, "freq_current": 0, "count_logical": 4, "load_avg": (1.0, 1.0, 1.0)},
        no_color=True,
    )
    assert "LD" not in quiet.plain
    busy = brief_mod._format_cpu(
        {"percent": 10, "freq_current": 0, "count_logical": 2, "load_avg": (2.5, 2.0, 1.0)},
        no_color=True,
    )
    assert "LD 2.50" in busy.plain


def test_format_cpu_tolerates_empty_record():
    assert brief_mod._format_cpu({}, no_color=True).plain == "CPU 0%"


def test_build_brief_line_passes_network_interfaces(monkeypatch):
    seen = _stub_brief_collectors(monkeypatch)
    brief_mod.build_brief_line(no_gpu=True, interfaces=("eth0",))
    assert seen["interfaces"] == ("eth0",)


def test_build_brief_line_cpu_color_uses_config_thresholds(monkeypatch):
    _stub_brief_collectors(monkeypatch, cpu_percent=15.0)
    line = brief_mod.build_brief_line(
        no_gpu=True,
        thresholds=ThresholdConfig(cpu_warn=10, cpu_critical=20),
    )
    styles = _span_styles_for(line, "15%")
    assert any("yellow" in style for style in styles)


def test_build_brief_line_shows_disk_only_under_pressure(monkeypatch):
    seen = {}

    def fake_collect(name, settings=None):
        assert name == "disk"
        return {"percent": seen.get("percent", 10.0)}

    monkeypatch.setattr(brief_mod, "collect", fake_collect)
    monkeypatch.setattr(
        brief_mod,
        "load_config",
        lambda: SysmonConfig(
            modules=ModuleConfig(
                cpu=False,
                memory=False,
                network=False,
                disk=True,
                gpu=False,
                process=False,
                sensors=False,
            )
        ),
    )
    quiet = brief_mod.build_brief_line(no_color=True)
    assert quiet.plain == "modules disabled"
    seen["percent"] = 91.0
    busy = brief_mod.build_brief_line(no_color=True)
    assert busy.plain == "DISK 91%"


def test_build_brief_line_includes_swap_when_in_use(monkeypatch):
    def fake_collect(name, settings=None):
        if name == "memory":
            return {
                "used": 1,
                "total": 2,
                "percent": 10.0,
                "swap_total": 100,
                "swap_percent": 25.0,
            }
        raise AssertionError(name)

    monkeypatch.setattr(brief_mod, "collect", fake_collect)
    monkeypatch.setattr(brief_mod, "bytes_to_gb", lambda n: 1.0)
    monkeypatch.setattr(
        brief_mod,
        "load_config",
        lambda: SysmonConfig(
            modules=ModuleConfig(
                cpu=False,
                memory=True,
                network=False,
                disk=False,
                gpu=False,
                process=False,
                sensors=False,
            )
        ),
    )
    line = brief_mod.build_brief_line(no_color=True)
    assert line.plain == "RAM 1.0/1.0G (10%) SWAP 25%"


def test_build_brief_line_ignores_non_numeric_swap_and_battery(monkeypatch):
    def fake_collect(name, settings=None):
        if name == "memory":
            return {"used": 1, "total": 2, "percent": 10.0, "swap_total": "bad", "swap_percent": "bad"}
        if name == "sensors":
            return {"battery": {"percent": "bad", "power_plugged": False}, "temperatures": {}}
        raise AssertionError(name)

    monkeypatch.setattr(brief_mod, "collect", fake_collect)
    monkeypatch.setattr(brief_mod, "bytes_to_gb", lambda n: 1.0)
    monkeypatch.setattr(
        brief_mod,
        "load_config",
        lambda: SysmonConfig(
            modules=ModuleConfig(
                cpu=False,
                memory=True,
                network=False,
                disk=False,
                gpu=False,
                process=False,
                sensors=True,
            )
        ),
    )
    line = brief_mod.build_brief_line(no_color=True)
    assert line.plain == "RAM 1.0/1.0G (10%)"


def test_build_brief_line_shows_down_interfaces(monkeypatch):
    def fake_collect(name, settings=None):
        assert name == "network"
        return {
            "speed_up": 0,
            "speed_down": 0,
            "interfaces": [
                {"name": "eth0", "isup": False},
                {"name": "wlan0", "isup": True},
                "bad",
            ],
        }

    monkeypatch.setattr(brief_mod, "collect", fake_collect)
    monkeypatch.setattr(
        brief_mod,
        "load_config",
        lambda: SysmonConfig(
            modules=ModuleConfig(
                cpu=False,
                memory=False,
                network=True,
                disk=False,
                gpu=False,
                process=False,
                sensors=False,
            )
        ),
    )
    line = brief_mod.build_brief_line(no_color=True)
    assert "DOWN eth0" in line.plain
    assert "wlan0" not in line.plain


def test_build_brief_line_memory_color_uses_memory_thresholds(monkeypatch):
    _stub_brief_collectors(monkeypatch, cpu_percent=1.0, memory_percent=15.0)
    line = brief_mod.build_brief_line(
        no_gpu=True,
        thresholds=ThresholdConfig(memory_warn=10, memory_critical=20),
    )
    styles = _span_styles_for(line, "(15%)")
    assert any("yellow" in style for style in styles)


def test_build_brief_line_shows_zero_gpu_temperature(monkeypatch):
    gpu = [
        {
            "load": 1.0,
            "memory_used": 1024,
            "memory_total": 2048,
            "temperature": 0,
        }
    ]
    _stub_brief_collectors(monkeypatch, gpu=gpu)
    line = brief_mod.build_brief_line(no_color=True)
    assert "0°C" in line.plain


def test_build_brief_line_gpu_load_uses_gpu_thresholds(monkeypatch):
    gpu = [
        {
            "load": 15.0,
            "memory_used": 1024,
            "memory_total": 2048,
            "temperature": 40,
        }
    ]
    _stub_brief_collectors(monkeypatch, gpu=gpu)
    line = brief_mod.build_brief_line(
        thresholds=ThresholdConfig(gpu_warn=10, gpu_critical=20),
    )
    styles = _span_styles_for(line, "GPU 15%")
    assert any("yellow" in style for style in styles)


def test_build_brief_line_skips_disabled_modules(monkeypatch):
    seen = []

    def fake_collect(name, settings=None):
        seen.append(name)
        if name == "memory":
            return {"used": 1, "total": 2, "percent": 10.0}
        raise AssertionError(name)

    monkeypatch.setattr(brief_mod, "collect", fake_collect)
    monkeypatch.setattr(brief_mod, "bytes_to_gb", lambda n: 1.0)
    monkeypatch.setattr(
        brief_mod,
        "load_config",
        lambda: SysmonConfig(
            modules=ModuleConfig(
                cpu=False,
                memory=True,
                network=False,
                disk=False,
                gpu=False,
                process=False,
                sensors=False,
            )
        ),
    )
    line = brief_mod.build_brief_line(no_gpu=False)
    assert seen == ["memory"]
    assert line.plain == "RAM 1.0/1.0G (10%)"


def test_build_brief_line_includes_battery_when_sensors_enabled(monkeypatch):
    def fake_collect(name, settings=None):
        assert name == "sensors"
        return {
            "battery": {"percent": 80.0, "power_plugged": True, "secsleft": None},
            "temperatures": {},
        }

    monkeypatch.setattr(brief_mod, "collect", fake_collect)
    monkeypatch.setattr(
        brief_mod,
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
    line = brief_mod.build_brief_line(no_color=True)
    assert line.plain == "BAT 80% AC"


def test_build_brief_line_includes_hottest_temperature(monkeypatch):
    def fake_collect(name, settings=None):
        assert name == "sensors"
        return {
            "battery": None,
            "temperatures": {
                "coretemp": [
                    {"label": "Package", "current": 70.2, "high": 80, "critical": 100},
                    {"label": "Core", "current": 91.0, "high": 80, "critical": 90},
                ]
            },
        }

    monkeypatch.setattr(brief_mod, "collect", fake_collect)
    monkeypatch.setattr(
        brief_mod,
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
    line = brief_mod.build_brief_line(no_color=True)
    assert line.plain == "TEMP 91°C"


def test_build_brief_line_empty_when_modules_disabled(monkeypatch):
    monkeypatch.setattr(
        brief_mod,
        "collect",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("collect")),
    )
    monkeypatch.setattr(
        brief_mod,
        "load_config",
        lambda: SysmonConfig(
            modules=ModuleConfig(
                cpu=False,
                memory=False,
                network=False,
                disk=False,
                gpu=False,
                process=False,
                sensors=False,
            )
        ),
    )
    line = brief_mod.build_brief_line(no_gpu=True)
    assert line.plain == "modules disabled"


def test_print_brief_passes_thresholds(monkeypatch):
    captured = {}
    thresholds = ThresholdConfig(cpu_warn=10, cpu_critical=20)
    monkeypatch.setattr(brief_mod, "collect", lambda *a, **k: None)

    def fake_line(*a, **k):
        captured["kwargs"] = k
        return "line"

    monkeypatch.setattr(brief_mod, "build_brief_line", fake_line)
    monkeypatch.setattr(brief_mod.time, "sleep", lambda s: None)

    console = Console(record=True)
    brief_mod.print_brief(console, no_gpu=True, thresholds=thresholds)
    assert captured["kwargs"]["thresholds"] is thresholds


def test_run_brief_watch_passes_thresholds(monkeypatch):
    captured = {}
    thresholds = ThresholdConfig(cpu_warn=10, cpu_critical=20)
    monkeypatch.setattr(brief_mod, "collect", lambda *a, **k: None)
    sleeps = {"n": 0}

    def fake_sleep(_s):
        sleeps["n"] += 1
        if sleeps["n"] > 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(brief_mod.time, "sleep", fake_sleep)

    def fake_line(*a, **k):
        captured["kwargs"] = k
        return "line"

    monkeypatch.setattr(brief_mod, "build_brief_line", fake_line)

    class _Live:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def update(self, _line):
            pass

    monkeypatch.setattr(brief_mod, "Live", _Live)
    console = Console(record=True)
    brief_mod.run_brief_watch(console, no_gpu=True, thresholds=thresholds)
    assert captured["kwargs"]["thresholds"] is thresholds


def test_run_brief_watch_skips_startup_wait_when_network_disabled(monkeypatch):
    slept: list[float] = []

    class _Live:
        def __init__(self, renderable, *a, **k):
            self.renderable = renderable

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def update(self, _line):
            return None

    monkeypatch.setattr(brief_mod, "collect", lambda *a, **k: None)
    monkeypatch.setattr(brief_mod, "build_brief_line", lambda *a, **k: "line")
    monkeypatch.setattr(brief_mod, "Live", _Live)
    monkeypatch.setattr(
        brief_mod,
        "load_config",
        lambda: SysmonConfig(
            modules=ModuleConfig(
                cpu=False,
                memory=False,
                network=False,
                disk=False,
                gpu=False,
                process=False,
                sensors=False,
            )
        ),
    )

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        raise KeyboardInterrupt

    monkeypatch.setattr(brief_mod.time, "sleep", fake_sleep)
    brief_mod.run_brief_watch(Console(), refresh_rate=2.0, no_gpu=True)
    assert slept == [2.0]


def test_run_brief_watch_survives_a_bad_refresh(monkeypatch):
    calls = {"n": 0}
    sleeps = {"n": 0}
    updates = []

    def fake_sleep(_s):
        sleeps["n"] += 1
        if sleeps["n"] >= 3:
            raise KeyboardInterrupt

    def fake_line(*_a, **_k):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("bad brief")
        return "line"

    class _Live:
        def __init__(self, renderable, *a, **k):
            self.renderable = renderable

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def update(self, line):
            updates.append(line)

    monkeypatch.setattr(brief_mod, "collect", lambda *a, **k: None)
    monkeypatch.setattr(brief_mod.time, "sleep", fake_sleep)
    monkeypatch.setattr(brief_mod, "build_brief_line", fake_line)
    monkeypatch.setattr(brief_mod, "Live", _Live)
    brief_mod.run_brief_watch(Console(record=True), no_gpu=True)
    assert calls["n"] >= 2
    assert any(getattr(item, "plain", "") == "brief error: bad brief" for item in updates)


def test_print_brief_survives_failed_network_prime(monkeypatch):
    monkeypatch.setattr(
        brief_mod,
        "collect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("down")),
    )
    monkeypatch.setattr(brief_mod, "build_brief_line", lambda *_args, **_kwargs: "ok")
    monkeypatch.setattr(
        brief_mod.time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(AssertionError("slept")),
    )
    brief_mod.print_brief(Console(), no_gpu=True)


def test_print_brief_skips_sample_wait_when_network_disabled(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(brief_mod, "collect", lambda *a, **k: None)
    monkeypatch.setattr(brief_mod, "build_brief_line", lambda *a, **k: "line")
    monkeypatch.setattr(brief_mod.time, "sleep", lambda seconds: slept.append(seconds))
    monkeypatch.setattr(
        brief_mod,
        "load_config",
        lambda: SysmonConfig(
            modules=ModuleConfig(
                cpu=True,
                memory=False,
                network=False,
                disk=False,
                gpu=False,
                process=False,
                sensors=False,
            )
        ),
    )
    brief_mod.print_brief(Console(), no_gpu=True, sample_interval=0.25)
    assert slept == []


def test_print_brief_uses_sample_interval(monkeypatch):
    slept = {}
    monkeypatch.setattr(brief_mod, "collect", lambda *a, **k: None)
    monkeypatch.setattr(brief_mod, "build_brief_line", lambda *a, **k: "line")
    monkeypatch.setattr(brief_mod.time, "sleep", lambda s: slept.setdefault("s", s))

    console = Console(record=True)
    brief_mod.print_brief(console, no_gpu=True, sample_interval=0.25, interfaces=None)
    assert slept["s"] == 0.25


def test_run_title_mode_inherits_stdout(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(brief_mod, "_PID_FILE", tmp_path / "title.pid")
    monkeypatch.setattr(brief_mod, "_LOCK_FILE", tmp_path / "title.lock")
    monkeypatch.setattr(brief_mod.time, "sleep", lambda s: None)

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _AliveProc()

    monkeypatch.setattr(brief_mod.subprocess, "Popen", fake_popen)

    console = Console(record=True)
    brief_mod.run_title_mode(console, refresh_rate=2.0, no_gpu=True)

    assert "stdout" not in captured["kwargs"]
    assert captured["kwargs"].get("stdout") is None
    assert captured["kwargs"]["stderr"] is subprocess.DEVNULL
    assert "start_new_session" not in captured["kwargs"]
    assert "--marker" in captured["cmd"]
    assert (tmp_path / "title.pid").read_text(encoding="utf-8") == "4242"
    assert "Title mode started" in console.export_text()


def test_run_title_mode_reports_immediate_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(brief_mod, "_PID_FILE", tmp_path / "title.pid")
    monkeypatch.setattr(brief_mod, "_LOCK_FILE", tmp_path / "title.lock")
    monkeypatch.setattr(brief_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(brief_mod.subprocess, "Popen", lambda *a, **k: _DeadProc())

    console = Console(record=True)
    brief_mod.run_title_mode(console)
    text = console.export_text()
    assert "exited immediately" in text
    assert not (tmp_path / "title.pid").exists()


def test_title_worker_command_uses_module_for_python():
    cmd = brief_mod.title_worker_command(2.0, True)
    assert "-m" in cmd
    assert "sysmon.display.title_worker" in cmd
    assert "--no-gpu" in cmd


def test_title_worker_command_uses_flag_when_frozen(monkeypatch):
    monkeypatch.setattr(brief_mod.sys, "frozen", True, raising=False)
    cmd = brief_mod.title_worker_command(1.5, True)
    assert "--title-worker" in cmd
    assert "--title-refresh" in cmd
    assert "--title-no-gpu" in cmd
    assert "-m" not in cmd
