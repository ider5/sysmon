"""Tests for sparkline rendering."""

from sysmon.display.sparkline import HistoryBuffer, render_sparkline


def test_history_buffer_maxlen():
    buf = HistoryBuffer(maxlen=3)
    for v in [1, 2, 3, 4]:
        buf.add(v)
    assert buf.values() == [2, 3, 4]


def test_history_buffer_ignores_non_finite_values():
    buf = HistoryBuffer(maxlen=4)
    buf.add(1.0)
    buf.add(float("nan"))
    buf.add(float("inf"))
    buf.add(True)  # type: ignore[arg-type]
    buf.add(2.0)
    assert buf.values() == [1.0, 2.0]


def test_render_sparkline_ignores_non_finite_values():
    assert render_sparkline([float("nan"), float("inf")], width=4) == " " * 4
    line = render_sparkline([float("nan"), 0.0, 100.0], width=4)
    assert len(line) == 4
    assert "▁" in line
    assert "█" in line


def test_render_sparkline_zero_width():
    assert render_sparkline([1.0, 2.0, 3.0], width=0) == ""
    assert render_sparkline([], width=0) == ""


def test_render_sparkline_empty():
    assert render_sparkline([], width=10) == " " * 10


def test_render_sparkline_keeps_the_newest_sample():
    values = [0.0] * 60 + [100.0]
    line = render_sparkline(values, width=30)
    assert line[-1] == "█"


def test_render_sparkline_pads_with_the_first_sample():
    line = render_sparkline([80.0], width=5)
    assert line == "▁" * 5


def test_render_sparkline_with_values():
    line = render_sparkline([0, 50, 100], width=10)
    assert len(line) == 10
    assert "▁" in line or "█" in line
