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
        assert service.get("cpu") is not None
        assert service.get("missing", "fallback") == "fallback"
    finally:
        service.stop()

    assert not service.running


def test_collector_service_respects_disabled_modules():
    config = SysmonConfig.from_mapping(
        {
            "modules": {
                "cpu": True,
                "memory": False,
                "network": False,
                "disk": False,
                "gpu": False,
                "process": False,
            }
        }
    )
    service = CollectorService(interval=0.1, include_gpu=False, config=config)
    service.start()
    try:
        time.sleep(0.15)
        snapshot = service.get_snapshot()
        assert "cpu" in snapshot
        assert "memory" not in snapshot
        assert "network" not in snapshot
    finally:
        service.stop()
