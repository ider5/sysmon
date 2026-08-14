"""Tests for collector background service."""

import time

import pytest

from sysmon.collectors.service import CollectorService
from sysmon.config import SysmonConfig


def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("timed out waiting for collector snapshot")


def test_collector_service_caches_snapshot():
    service = CollectorService(
        interval=0.1,
        include_gpu=False,
        config=SysmonConfig(),
    )
    service.start()
    try:
        _wait_until(lambda: service.get("cpu") is not None)
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
        _wait_until(lambda: "cpu" in service.get_snapshot())
        snapshot = service.get_snapshot()
        assert "cpu" in snapshot
        assert "memory" not in snapshot
        assert "network" not in snapshot
    finally:
        service.stop()


def test_start_resets_running_after_collect_failure(monkeypatch):
    service = CollectorService(
        interval=10,
        include_gpu=False,
        config=SysmonConfig(),
    )
    original = service._collect_once
    calls = {"n": 0}

    def flaky() -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("collect failed")
        original()

    monkeypatch.setattr(service, "_collect_once", flaky)
    with pytest.raises(RuntimeError, match="collect failed"):
        service.start()
    assert service.running is False

    service.start()
    assert service.running is True
    service.stop()


def test_module_failure_keeps_other_metrics(monkeypatch):
    def boom():
        raise RuntimeError("cpu down")

    monkeypatch.setattr("sysmon.collectors.cpu.get_cpu_snapshot", boom)
    service = CollectorService(
        interval=10,
        include_gpu=False,
        config=SysmonConfig(),
    )
    service.start()
    try:
        snapshot = service.get_snapshot()
        assert "memory" in snapshot
        assert "cpu" not in snapshot
        assert "cpu" in snapshot.get("errors", {})
    finally:
        service.stop()


def test_collector_service_calls_registry_collect_not_cpu_snapshot(monkeypatch):
    calls = []

    def fake_collect(name, settings=None):
        calls.append((name, settings))
        return {name: "stub"}

    cpu_direct_calls = []

    def fake_get_cpu_snapshot():
        cpu_direct_calls.append(True)
        return {"percent": 0}

    monkeypatch.setattr("sysmon.collectors.registry.collect", fake_collect)
    monkeypatch.setattr("sysmon.collectors.cpu.get_cpu_snapshot", fake_get_cpu_snapshot)

    config = SysmonConfig.from_mapping(
        {
            "modules": {
                "cpu": True,
                "memory": True,
                "network": False,
                "disk": False,
                "gpu": False,
                "process": False,
            }
        }
    )
    service = CollectorService(interval=10, include_gpu=False, config=config)
    service.start()
    try:
        assert calls == [("cpu", config), ("memory", config)]
        assert cpu_direct_calls == []
    finally:
        service.stop()
