"""Tests for display components."""

from pathlib import Path

from sysmon.display import components
from sysmon.display.components import gpu_panel, gradient_color, progress_bar


def test_gradient_color_thresholds():
    assert gradient_color(30) == "green"
    assert gradient_color(70) == "yellow"
    assert gradient_color(90) == "yellow"
    assert gradient_color(98, critical=95) == "red"


def test_progress_bar_contains_percentage():
    bar = progress_bar(42.5, width=10)
    assert "42.5%" in str(bar)


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
