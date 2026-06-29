"""Tests for sparkline rendering."""

from sysmon.display.sparkline import HistoryBuffer, render_sparkline


def test_history_buffer_maxlen():
    buf = HistoryBuffer(maxlen=3)
    for v in [1, 2, 3, 4]:
        buf.add(v)
    assert buf.values() == [2, 3, 4]


def test_render_sparkline_empty():
    assert render_sparkline([], width=10) == " " * 10


def test_render_sparkline_with_values():
    line = render_sparkline([0, 50, 100], width=10)
    assert len(line) == 10
    assert "▁" in line or "█" in line
