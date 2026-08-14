"""Tests for shared display panels."""

from rich.console import Console

from sysmon.display.panels import (
    build_cpu_text,
    build_disk_text,
    build_memory_text,
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
