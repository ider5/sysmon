"""Tests for display components."""

from sysmon.display.components import gradient_color, progress_bar


def test_gradient_color_thresholds():
    assert gradient_color(30) == "green"
    assert gradient_color(70) == "yellow"
    assert gradient_color(90) == "red"


def test_progress_bar_contains_percentage():
    bar = progress_bar(42.5, width=10)
    assert "42.5%" in str(bar)
