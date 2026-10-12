"""Tests for terminal title worker helpers."""

from __future__ import annotations

from sysmon.config import ModuleConfig, SysmonConfig
from sysmon.display import title_worker
from sysmon.display.title_worker import osc_title_sequence, sanitize_title


def test_sanitize_title_strips_osc_breakers():
    cleaned = sanitize_title("CPU 10%\033]0;evil\007")
    assert "\033" not in cleaned
    assert "\007" not in cleaned
    assert "CPU 10%" in cleaned


def test_osc_title_sequence_wraps_sanitized_text():
    seq = osc_title_sequence("RAM 1/2G")
    assert seq.startswith("\033]0;")
    assert seq.endswith("\007")
    assert "RAM 1/2G" in seq


def test_build_title_tolerates_empty_cpu_record(monkeypatch):
    monkeypatch.setattr(title_worker, "collect", lambda name, settings=None: {})
    monkeypatch.setattr(
        title_worker,
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
    assert title_worker.build_title(no_gpu=True) == "CPU 0%"


def test_build_title_shows_zero_gpu_temperature(monkeypatch):
    def fake_collect(name, settings=None):
        assert name == "gpu"
        return [
            {
                "load": 1.0,
                "memory_used": 1024.0,
                "memory_total": 2048.0,
                "temperature": 0,
            }
        ]

    monkeypatch.setattr(title_worker, "collect", fake_collect)
    monkeypatch.setattr(
        title_worker,
        "load_config",
        lambda: SysmonConfig(
            modules=ModuleConfig(
                cpu=False,
                memory=False,
                network=False,
                disk=False,
                gpu=True,
                process=False,
                sensors=False,
            )
        ),
    )
    assert "0°C" in title_worker.build_title(no_gpu=False)


def test_build_title_shows_disk_only_under_pressure(monkeypatch):
    seen = {"percent": 10.0}

    def fake_collect(name, settings=None):
        assert name == "disk"
        return {"percent": seen["percent"]}

    monkeypatch.setattr(title_worker, "collect", fake_collect)
    monkeypatch.setattr(
        title_worker,
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
    assert title_worker.build_title(no_gpu=True) == "sysmon"
    seen["percent"] = 90.0
    assert title_worker.build_title(no_gpu=True) == "DISK 90%"


def test_build_title_includes_swap_when_in_use(monkeypatch):
    def fake_collect(name, settings=None):
        assert name == "memory"
        return {
            "used": 1,
            "total": 2,
            "percent": 10.0,
            "swap_total": 100,
            "swap_percent": 25.0,
        }

    monkeypatch.setattr(title_worker, "collect", fake_collect)
    monkeypatch.setattr(title_worker, "bytes_to_gb", lambda n: 1.0)
    monkeypatch.setattr(
        title_worker,
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
    assert title_worker.build_title(no_gpu=True) == "RAM 1.0/1.0G (10%) SWAP 25%"


def test_build_title_follows_modules_and_battery(monkeypatch):
    def fake_collect(name, settings=None):
        assert name == "sensors"
        return {
            "battery": {"percent": 42.0, "power_plugged": False, "secsleft": 10},
            "temperatures": {},
        }

    monkeypatch.setattr(title_worker, "collect", fake_collect)
    monkeypatch.setattr(
        title_worker,
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
    assert title_worker.build_title(no_gpu=False) == "BAT 42%"


def test_build_title_includes_hottest_temperature(monkeypatch):
    def fake_collect(name, settings=None):
        assert name == "sensors"
        return {
            "battery": {"percent": 42.0, "power_plugged": False, "secsleft": 10},
            "temperatures": {"coretemp": [{"label": "Package", "current": 55.6}]},
        }

    monkeypatch.setattr(title_worker, "collect", fake_collect)
    monkeypatch.setattr(
        title_worker,
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
    assert title_worker.build_title(no_gpu=True) == "BAT 42% │ TEMP 56°C"


def test_build_title_placeholder_when_nothing_enabled(monkeypatch):
    monkeypatch.setattr(
        title_worker,
        "collect",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("collect")),
    )
    monkeypatch.setattr(
        title_worker,
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
    assert title_worker.build_title(no_gpu=True) == "sysmon"


def test_set_title_writes_osc_to_stdout(monkeypatch):
    import io

    buf = io.StringIO()
    buf.isatty = lambda: True  # type: ignore[method-assign]
    monkeypatch.setattr("sysmon.display.title_worker.sys.stdout", buf)
    monkeypatch.setattr("sysmon.display.title_worker.sys.platform", "linux")

    from sysmon.display.title_worker import set_title

    set_title("CPU 10%")
    assert "\033]0;CPU 10%\007" in buf.getvalue()
