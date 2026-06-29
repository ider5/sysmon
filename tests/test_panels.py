"""Tests for shared display panels."""

from sysmon.display.panels import build_cpu_text, build_disk_text, build_memory_text


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
