"""Tests for terminal title worker helpers."""

from __future__ import annotations

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
