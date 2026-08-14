"""Tests for brief mode helpers and title-mode startup."""

from __future__ import annotations

import subprocess

from rich.console import Console

from sysmon.display import brief as brief_mod


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

    monkeypatch.setattr(
        brief_mod,
        "get_cpu_info",
        lambda: {"percent": 1.0, "freq_current": 0},
    )
    monkeypatch.setattr(
        brief_mod,
        "get_memory_info",
        lambda: {"used": 1, "total": 2, "percent": 50},
    )
    monkeypatch.setattr(brief_mod, "get_gpu_info", lambda: None)

    def fake_net(interfaces=None):
        seen["interfaces"] = interfaces
        return {
            "speed_up": 0,
            "speed_down": 0,
            "bytes_sent": 0,
            "bytes_recv": 0,
        }

    monkeypatch.setattr(brief_mod, "get_network_info", fake_net)
    monkeypatch.setattr(brief_mod, "bytes_to_gb", lambda n: 1.0)
    monkeypatch.setattr(brief_mod, "format_speed", lambda n: "0 B/s")

    brief_mod.build_brief_line(no_gpu=True, interfaces=("eth0",))
    assert seen["interfaces"] == ("eth0",)


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
