"""Tests for shared display panels."""

from rich.console import Console

from sysmon.display.panels import (
    build_cpu_text,
    build_disk_text,
    build_memory_text,
    build_sensors_text,
    process_panel,
)


def test_build_cpu_text_includes_usage():
    info = {
        "percent": 42.0,
        "count_physical": 8,
        "count_logical": 16,
        "freq_current": 3200,
    }
    text = build_cpu_text(info)
    assert "42.0%" in str(text)
    assert "8 cores / 16 threads" in str(text)


def test_build_memory_text_includes_history():
    info = {
        "percent": 50.0,
        "used": 8 * 1024 ** 3,
        "total": 16 * 1024 ** 3,
        "available": 8 * 1024 ** 3,
        "swap_total": 0,
        "swap_used": 0,
        "swap_percent": 0.0,
    }
    text = build_memory_text(info, history=[10.0, 50.0, 90.0])
    rendered = text.plain
    assert "History" in rendered
    assert "▁" in rendered or "█" in rendered


def test_build_memory_text_includes_ram():
    info = {
        "percent": 50.0,
        "used": 8 * 1024 ** 3,
        "total": 16 * 1024 ** 3,
        "available": 8 * 1024 ** 3,
        "swap_total": 0,
        "swap_used": 0,
        "swap_percent": 0.0,
    }
    text = build_memory_text(info, show_available=True)
    rendered = str(text)
    assert "8.0 / 16.0 GB" in rendered
    assert "Available" in rendered


def test_build_disk_text_includes_speed_history():
    info = {
        "mount": "/",
        "percent": 10.0,
        "used": 10,
        "total": 100,
        "read_speed": 2048,
        "write_speed": 1024,
    }
    text = build_disk_text(info, read_history=[0.0, 2048.0], write_history=[0.0, 1024.0])
    rendered = text.plain
    assert "2.0 KB/s" in rendered
    assert "1.0 KB/s" in rendered
    assert "▁" in rendered
    assert "█" in rendered


def test_build_disk_text_includes_mount():
    info = {
        "mount": "C:\\",
        "percent": 70.0,
        "used": 100,
        "total": 200,
        "read_speed": 1024,
        "write_speed": 512,
    }
    text = build_disk_text(info)
    rendered = str(text)
    assert "C:\\" in rendered
    assert "70.0%" in rendered


def _render_panel(panel, **console_kwargs) -> str:
    console = Console(width=80, force_terminal=True, color_system=None, **console_kwargs)
    with console.capture() as capture:
        console.print(panel)
    return capture.get()


def _assert_process_table_frame(rendered: str) -> None:
    assert "PID" in rendered
    has_heavy = rendered.count("┃") >= 6 and ("┳" in rendered or "╋" in rendered)
    has_legacy = rendered.count("│") >= 6 and ("┬" in rendered or "┼" in rendered)
    assert has_heavy or has_legacy
    assert "┃  1 ┃" in rendered or "│  1 │" in rendered


def test_process_panel_renders_bordered_table():
    panel = process_panel(
        [
            {
                "pid": 4242,
                "name": "python",
                "cpu_percent": 12.3,
                "memory_percent": 1.5,
                "memory_mb": 50.7,
            }
        ],
        sort_by="cpu",
    )
    rendered = _render_panel(panel)
    assert "Name" in rendered
    assert "CPU%" in rendered
    assert "MEM%" in rendered
    assert "RSS" in rendered
    assert "4242" in rendered
    assert "python" in rendered
    assert "12.3" in rendered
    assert "1.5%" in rendered
    assert "51M" in rendered
    _assert_process_table_frame(rendered)
    assert "━" in rendered


def test_process_panel_legacy_windows_still_has_table_frame():
    rendered = _render_panel(
        process_panel(
            [
                {
                    "pid": 4242,
                    "name": "python",
                    "cpu_percent": 12.3,
                    "memory_percent": 1.5,
                    "memory_mb": 50.7,
                }
            ]
        ),
        legacy_windows=True,
    )
    _assert_process_table_frame(rendered)
    assert "4242" in rendered
    assert "python" in rendered


def test_process_panel_empty_still_has_table_frame():
    rendered = _render_panel(process_panel([]))
    assert "PID" in rendered
    assert "No matching processes" in rendered
    assert ("┳" in rendered or "╋" in rendered) or ("┬" in rendered or "┼" in rendered)


def test_build_sensors_text_battery_and_temperature():
    text = build_sensors_text(
        {
            "battery": {
                "percent": 80.0,
                "secsleft": 3700,
                "power_plugged": False,
            },
            "temperatures": {
                "coretemp": [
                    {
                        "label": "Package",
                        "current": 105.0,
                        "high": 80.0,
                        "critical": 100.0,
                    }
                ]
            },
        }
    )
    plain = text.plain
    assert "80.0%" in plain
    assert "on battery" in plain
    assert "1h 1m" in plain
    assert "Package" in plain
    assert "105.0°C" in plain
    temp_at = plain.index("105.0°C")
    covering = [
        span for span in text.spans if span.start <= temp_at < span.end
    ]
    assert covering
    assert "red" in str(covering[-1].style)


def test_build_sensors_text_empty_readings():
    text = build_sensors_text({"battery": None, "temperatures": {}})
    assert "No battery or temperature sensors" in text.plain
