"""Tests for brief mode helpers and title-mode startup."""

from __future__ import annotations

import subprocess

from rich.console import Console

from sysmon.config import ThresholdConfig
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
):
    monkeypatch.setattr(
        brief_mod,
        "get_cpu_info",
        lambda: {"percent": cpu_percent, "freq_current": 0},
    )
    monkeypatch.setattr(
        brief_mod,
        "get_memory_info",
        lambda: {"used": 1, "total": 2, "percent": memory_percent},
    )
    monkeypatch.setattr(brief_mod, "get_gpu_info", lambda: gpu)
    monkeypatch.setattr(
        brief_mod,
        "get_network_info",
        lambda interfaces=None: {
            "speed_up": 0,
            "speed_down": 0,
            "bytes_sent": 0,
            "bytes_recv": 0,
        },
    )
    monkeypatch.setattr(brief_mod, "bytes_to_gb", lambda n: 1.0)
    monkeypatch.setattr(brief_mod, "format_speed", lambda n: "0 B/s")


class _AliveProc:
    pid = 4242

    def poll(self):
        return None


class _DeadProc:
    pid = 7

    def poll(self):
        return 1


def test_build_brief_line_passes_network_interfaces(monkeypatch):
    seen = {}
    _stub_brief_collectors(monkeypatch)

    def fake_net(interfaces=None):
        seen["interfaces"] = interfaces
        return {
            "speed_up": 0,
            "speed_down": 0,
            "bytes_sent": 0,
            "bytes_recv": 0,
        }

    monkeypatch.setattr(brief_mod, "get_network_info", fake_net)

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


def test_build_brief_line_memory_color_uses_memory_thresholds(monkeypatch):
    _stub_brief_collectors(monkeypatch, cpu_percent=1.0, memory_percent=15.0)
    line = brief_mod.build_brief_line(
        no_gpu=True,
        thresholds=ThresholdConfig(memory_warn=10, memory_critical=20),
    )
    styles = _span_styles_for(line, "(15%)")
    assert any("yellow" in style for style in styles)


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


def test_print_brief_passes_thresholds(monkeypatch):
    captured = {}
    thresholds = ThresholdConfig(cpu_warn=10, cpu_critical=20)
    monkeypatch.setattr(brief_mod, "get_network_info", lambda *a, **k: None)

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
    monkeypatch.setattr(brief_mod, "get_network_info", lambda *a, **k: None)
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


def test_print_brief_uses_sample_interval(monkeypatch):
    slept = {}
    monkeypatch.setattr(brief_mod, "get_network_info", lambda *a, **k: None)
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
