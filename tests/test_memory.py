"""Tests for memory helpers."""

from sysmon.collectors.memory import bytes_to_gb


def test_bytes_to_gb():
    assert bytes_to_gb(1024 ** 3) == "1.0"
    assert bytes_to_gb(2.5 * 1024 ** 3) == "2.5"
