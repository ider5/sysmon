"""Shared pytest fixtures for sysmon tests."""

from __future__ import annotations

import pytest

from sysmon.config import clear_config_cache


@pytest.fixture(autouse=True)
def _clear_config_cache_between_tests():
    """Keep load_config cache from leaking across tests that swap paths."""
    clear_config_cache()
    yield
    clear_config_cache()
