"""Tests for collector background service."""

import time

from sysmon.collectors.service import CollectorService
from sysmon.config import SysmonConfig


def test_collector_service_caches_snapshot():
    service = CollectorService(
        interval=0.1,
        include_gpu=False,
        config=SysmonConfig(),
    )
    service.start()
    try:
        time.sleep(0.2)
        snapshot = service.get_snapshot()
        assert "timestamp" in snapshot
        assert "cpu" in snapshot
        assert "memory" in snapshot
    finally:
        service.stop()

    assert not service.running
