"""Tests for display components."""

from pathlib import Path

from sysmon.display import components
from sysmon.display.components import (
    celsius,
    gpu_panel,
    gradient_color,
    one_line,
    progress_bar,
)


def test_header_bar_keeps_labels_on_one_line():
    from sysmon.display.components import header_bar

    panel = header_bar("box\nname", "Linux\nextra", "1h\n2m")
    plain = panel.renderable.plain
    assert "box name" in plain
    assert "Linux extra" in plain
    assert "1h 2m" in plain
    assert "\n" not in plain


def test_one_line_collapses_whitespace():
    assert one_line("eth0\nextra", "unknown") == "eth0 extra"
    assert one_line("   ", "unknown") == "unknown"
    assert one_line(None, "?") == "?"


def test_celsius_rejects_non_finite():
    assert celsius(0) == 0.0
    assert celsius(-1) is None
    assert celsius(float("inf")) is None
    assert celsius(float("nan")) is None
    assert celsius(True) is None


def test_gradient_color_thresholds():
    assert gradient_color(30) == "green"
    assert gradient_color(70) == "green"
    assert gradient_color(90) == "yellow"
    assert gradient_color(98, critical=95) == "red"


def test_gpu_panel_uses_warn_critical_for_load():
    gpus = [
        {
            "id": 0,
            "name": "Fake",
            "load": 15.0,
            "memory_used": 100.0,
            "memory_total": 1000.0,
            "temperature": 40.0,
        }
    ]
    panel = gpu_panel(gpus, warn=10.0, critical=20.0)
    text = str(panel.renderable)
    assert "15.0%" in text or "15.0" in text
    styles = [
        str(span.style)
        for span in panel.renderable.spans
        if span.start < span.end
    ]
    assert any("yellow" in style for style in styles)


def test_progress_bar_non_finite_is_not_a_crash():
    bar = progress_bar(float("nan"), width=4)
    rendered = str(bar)
    assert "n/a" in rendered
    assert "━" not in rendered


def test_progress_bar_contains_percentage():
    bar = progress_bar(42.5, width=10)
    assert "42.5%" in str(bar)


def test_progress_bar_clamps_fill_above_100_percent():
    bar = progress_bar(250.0, width=10)
    rendered = str(bar)
    assert "250.0%" in rendered
    assert rendered.count("━") == 10
    assert rendered.count("─") == 0


def test_gpu_panel_shows_zero_celsius():
    panel = gpu_panel(
        [
            {
                "id": 0,
                "name": "Cold",
                "load": 0.0,
                "memory_used": 0.0,
                "memory_total": 100.0,
                "temperature": 0.0,
            }
        ]
    )
    assert "0°C" in str(panel.renderable)


def test_uptime_is_unknown_when_boot_time_fails(monkeypatch):
    def boom() -> float:
        raise OSError("boot")

    monkeypatch.setattr(components.psutil, "boot_time", boom)
    assert components._get_uptime() == "unknown"


def test_uptime_is_zero_when_boot_time_is_ahead(monkeypatch):
    monkeypatch.setattr(components.psutil, "boot_time", lambda: 200.0)
    monkeypatch.setattr(components.time, "time", lambda: 100.0)
    assert components._get_uptime() == "0m"


def test_gpu_panel_tolerates_partial_record():
    panel = gpu_panel([{}])
    rendered = str(panel.renderable)
    assert "GPU" in rendered
    assert "0.0%" in rendered
    assert "0 / 0 MB" in rendered


def test_gpu_panel_empty_list_shows_unavailable():
    panel = gpu_panel([])
    assert "No GPU" in str(panel.renderable)


def test_unused_helpers_removed_from_components():
    assert not hasattr(components, "color_percent")
    assert not hasattr(components, "metric_row")


def test_unused_helpers_have_no_callers_in_sysmon():
    root = Path(__file__).resolve().parents[1] / "sysmon"
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "color_percent" in text or "metric_row" in text:
            offenders.append(str(path.relative_to(root.parent)))
    assert offenders == []
