"""Tests for shared display panels."""

from rich.console import Console

from sysmon.display.panels import (
    build_cpu_text,
    build_disk_text,
    build_memory_text,
    build_network_text,
    build_sensors_text,
    process_panel,
)


def test_build_cpu_and_memory_text_tolerate_empty_records():
    cpu = build_cpu_text({})
    memory = build_memory_text({}, show_available=True)
    assert "0 cores / 0 threads" in cpu.plain
    assert "0.0 / 0.0 GB" in memory.plain
    assert "Available" in memory.plain
    assert "Swap" not in memory.plain


def test_build_cpu_text_shows_load_average():
    info = {
        "percent": 10.0,
        "count_physical": 2,
        "count_logical": 4,
        "freq_current": 0,
        "load_avg": (1.5, 1.0, 0.5),
    }
    text = build_cpu_text(info)
    assert "Load" in text.plain
    assert "1.50 1.00 0.50" in text.plain


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


def test_build_cpu_text_shows_per_core_outside_compact_mode():
    info = {
        "percent": 42.0,
        "count_physical": 2,
        "count_logical": 2,
        "freq_current": 3200,
    }
    text = build_cpu_text(info, cores=[10.0, 90.0], compact=False)
    rendered = text.plain
    assert "Per-core Usage" in rendered
    assert "10.0%" in rendered
    assert "90.0%" in rendered


def test_build_cpu_text_ignores_non_list_cores():
    info = {"percent": 10.0, "count_physical": 1, "count_logical": 1}
    text = build_cpu_text(info, cores=4)  # type: ignore[arg-type]
    assert "10.0%" in text.plain
    assert "Per-core Usage" not in text.plain


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


def test_cpu_memory_network_panels_tolerate_non_record():
    assert "0.0%" in build_cpu_text(None).plain  # type: ignore[arg-type]
    assert "0.0 / 0.0 GB" in build_memory_text(None).plain  # type: ignore[arg-type]
    assert "0.0 B/s" in build_network_text(None).plain  # type: ignore[arg-type]


def test_build_network_text_skips_divider_before_first_interface():
    text = build_network_text(
        {
            "speed_up": 0,
            "speed_down": 0,
            "interfaces": ["bad", {"name": "eth0", "speed_up": 0, "speed_down": 0}],
        }
    )
    plain = text.plain
    assert "eth0" in plain
    assert plain.index("eth0") < plain.index("─")


def test_build_network_text_shows_link_down():
    text = build_network_text(
        {"interfaces": [{"name": "eth0", "speed_up": 0, "speed_down": 0, "isup": False}]}
    )
    assert "State" in text.plain
    assert "down" in text.plain.split("State", 1)[1]
    up = build_network_text(
        {"interfaces": [{"name": "eth0", "speed_up": 0, "speed_down": 0, "isup": True}]}
    )
    assert "State" not in up.plain


def test_build_network_text_shows_link_speed():
    text = build_network_text(
        {
            "speed_up": 0,
            "speed_down": 0,
            "bytes_sent": 0,
            "bytes_recv": 0,
            "interfaces": [{"name": "eth0", "speed_up": 0, "speed_down": 0, "speed_mbps": 1000}],
        }
    )
    assert "1000 Mb/s" in text.plain


def test_build_network_text_ignores_non_finite_link_speed():
    text = build_network_text(
        {
            "interfaces": [
                {"name": "bad0", "speed_up": 0, "speed_down": 0, "speed_mbps": float("inf")},
                {"name": "huge0", "speed_up": 0, "speed_down": 0, "speed_mbps": 1e308},
                {"name": "eth0", "speed_up": 0, "speed_down": 0, "speed_mbps": 1000},
            ]
        }
    )
    assert "1000 Mb/s" in text.plain
    assert "inf" not in text.plain


def test_build_network_text_shows_per_interface_errors():
    text = build_network_text(
        {
            "speed_up": 0,
            "speed_down": 0,
            "bytes_sent": 0,
            "bytes_recv": 0,
            "errin": 2,
            "errout": 0,
            "dropin": 0,
            "dropout": 0,
            "interfaces": [
                {
                    "name": "eth0",
                    "speed_up": 0,
                    "speed_down": 0,
                    "errin": 2,
                    "errout": 0,
                    "dropin": 0,
                    "dropout": 0,
                }
            ],
        }
    )
    assert text.plain.count("Errors") == 2
    assert "eth0" in text.plain


def test_build_network_text_shows_nonzero_errors():
    text = build_network_text(
        {
            "speed_up": 0,
            "speed_down": 0,
            "bytes_sent": 0,
            "bytes_recv": 0,
            "errin": 2,
            "errout": 0,
            "dropin": 1,
            "dropout": 0,
        }
    )
    assert "Errors" in text.plain
    assert "in 2 out 0 drop 1/0" in text.plain


def test_build_network_text_tolerates_partial_record():
    text = build_network_text({"interfaces": [{"name": "eth0"}]}, show_packets=True)
    rendered = text.plain
    assert "eth0" in rendered
    assert "0.0 B/s" in rendered
    assert "Packets" in rendered


def test_build_network_text_includes_upload_history():
    info = {
        "speed_up": 2048,
        "speed_down": 1024,
        "bytes_sent": 10,
        "bytes_recv": 20,
        "packets_sent": 1,
        "packets_recv": 2,
    }
    text = build_network_text(info, upload_history=[0.0, 2048.0])
    rendered = text.plain
    assert "2.0 KB/s" in rendered
    assert "▁" in rendered
    assert "█" in rendered


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


def test_build_disk_text_shows_filesystem_type():
    info = {
        "read_speed": 0,
        "write_speed": 0,
        "mounts": [
            {
                "mount": "/data",
                "percent": 10.0,
                "used": 1,
                "free": 9,
                "total": 10,
                "fstype": "ext4",
            }
        ],
    }
    assert "/data (ext4)" in build_disk_text(info).plain


def test_build_disk_text_shows_inode_usage():
    info = {
        "mount": "/",
        "percent": 10.0,
        "used": 10,
        "free": 90,
        "total": 100,
        "read_speed": 0,
        "write_speed": 0,
        "inode_percent": 75.0,
        "mounts": [
            {
                "mount": "/",
                "percent": 10.0,
                "used": 10,
                "free": 90,
                "total": 100,
                "inode_percent": 75.0,
            }
        ],
    }
    assert "Inodes" in build_disk_text(info).plain
    assert "75.0%" in build_disk_text(info).plain


def test_build_disk_text_shows_free_space():
    info = {
        "mount": "/",
        "percent": 50.0,
        "used": 50,
        "free": 50,
        "total": 100,
        "read_speed": 0,
        "write_speed": 0,
        "mounts": [
            {"mount": "/", "percent": 50.0, "used": 50, "free": 50, "total": 100}
        ],
    }
    text = build_disk_text(info)
    assert "Free" in text.plain
    assert "50.0 B" in text.plain


def test_build_disk_text_tolerates_partial_mount():
    info = {
        "mounts": [{"free": None}],
    }
    text = build_disk_text(info)
    assert "0.0 B / 0.0 B" in text.plain
    assert "Free" not in text.plain


def test_build_disk_text_skips_non_record_mounts():
    text = build_disk_text(
        {
            "read_speed": float("inf"),
            "write_speed": float("nan"),
            "mounts": [
                "bad",
                {
                    "mount": "/",
                    "percent": 12.0,
                    "used": float("inf"),
                    "total": 100,
                    "free": float("nan"),
                },
            ],
        }
    )
    plain = text.plain
    assert "/" in plain
    assert "12.0%" in plain
    assert "0.0 B / 100.0 B" in plain
    assert "Free" not in plain
    assert "inf" not in plain
    assert "nan" not in plain


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


def test_process_panel_memory_color_uses_memory_thresholds():
    panel = process_panel(
        [
            {
                "pid": 1,
                "name": "a",
                "cpu_percent": 1.0,
                "memory_percent": 15.0,
                "memory_mb": 10.0,
            }
        ],
        warn=80.0,
        critical=95.0,
        mem_warn=10.0,
        mem_critical=20.0,
    )
    table = panel.renderable
    cell = table.columns[4]._cells[0]
    assert "yellow" in str(cell.style)


def test_process_panel_shows_markup_name_as_text():
    panel = process_panel(
        [
            {
                "pid": 1,
                "name": "[red]x[/red]\nmore",
                "cpu_percent": 0,
                "memory_percent": 0,
                "memory_mb": 0,
            }
        ],
        name_filter="[/bold]",
    )
    rendered = _render_panel(panel)
    assert "[red]x[/red] more" in rendered
    assert "filter:" in rendered
    assert "\\[/bold]" in str(panel.title)


def test_process_panel_ignores_non_dict_rows():
    rendered = _render_panel(process_panel([None, "python"]))  # type: ignore[list-item]
    assert "No matching processes" in rendered


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


def test_build_sensors_text_tolerates_partial_record():
    text = build_sensors_text(
        {
            "battery": {"percent": "bad", "secsleft": True, "power_plugged": False},
            "temperatures": {
                "coretemp": [
                    {"label": "Package", "current": True, "high": True, "critical": True},
                    {"label": "Zero", "current": 0.0},
                ]
            },
        }
    )
    plain = text.plain
    assert "n/a" in plain
    assert "1.0°C" not in plain
    assert "0.0°C" in plain
    assert "Remaining" not in plain


def test_build_sensors_text_shows_hottest_readings_first():
    temperatures = {
        "group": [{"label": f"t{index}", "current": 10.0 + index} for index in range(8)]
    }
    temperatures["group"].append({"label": "hottest", "current": 99.0})
    temperatures["group"].append({"label": "missing", "current": None})
    text = build_sensors_text({"battery": None, "temperatures": temperatures})
    plain = text.plain
    assert plain.index("hottest") < plain.index("t7")
    assert "99.0°C" in plain
    assert "t0" not in plain
    assert "missing" not in plain
    assert "+2 more" in plain


def test_build_sensors_text_rejects_non_record():
    text = build_sensors_text(None)  # type: ignore[arg-type]
    assert "No battery or temperature sensors" in text.plain
