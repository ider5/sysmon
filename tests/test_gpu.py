"""Tests for GPU collector backends."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from sysmon.collectors import gpu as gpu_mod


def test_get_gpu_info_prefers_pynvml(monkeypatch):
    fake = [
        {
            "id": 0,
            "name": "NV",
            "load": 11.0,
            "memory_total": 4096.0,
            "memory_used": 512.0,
            "temperature": 40.0,
            "backend": "pynvml",
        }
    ]
    monkeypatch.setattr(gpu_mod, "_get_gpu_info_pynvml", lambda: fake)
    monkeypatch.setattr(
        gpu_mod,
        "_get_gpu_info_gputil",
        lambda: (_ for _ in ()).throw(AssertionError("should not fallback")),
    )
    assert gpu_mod.get_gpu_info() == fake


def test_get_gpu_info_falls_back_to_gputil(monkeypatch):
    fake = [
        {
            "id": 1,
            "name": "GT",
            "load": 22.0,
            "memory_total": 8192.0,
            "memory_used": 1024.0,
            "temperature": 55.0,
            "backend": "gputil",
        }
    ]
    monkeypatch.setattr(gpu_mod, "_get_gpu_info_pynvml", lambda: None)
    monkeypatch.setattr(gpu_mod, "_get_gpu_info_gputil", lambda: fake)
    assert gpu_mod.get_gpu_info() == fake


def test_get_gpu_info_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(gpu_mod, "_get_gpu_info_pynvml", lambda: None)
    monkeypatch.setattr(gpu_mod, "_get_gpu_info_gputil", lambda: None)
    assert gpu_mod.get_gpu_info() is None


def test_gputil_backend_maps_fields(monkeypatch):
    class _Gpu:
        id = 0
        name = "FakeGTX"
        load = 0.25
        memoryTotal = 2048.0
        memoryUsed = 256.0
        temperature = 61.0

    monkeypatch.setattr(gpu_mod, "_get_gpu_info_pynvml", lambda: None)

    fake_mod = SimpleNamespace(getGPUs=lambda: [_Gpu()])
    monkeypatch.setitem(__import__("sys").modules, "GPUtil", fake_mod)

    result = gpu_mod._get_gpu_info_gputil()
    assert result is not None
    assert result[0]["name"] == "FakeGTX"
    assert result[0]["load"] == 25.0
    assert result[0]["backend"] == "gputil"


def test_pynvml_init_once_and_maps_fields(monkeypatch):
    counts = {"init": 0, "shutdown": 0}
    handle = object()

    fake = SimpleNamespace(
        NVML_TEMPERATURE_GPU=0,
        nvmlInit=lambda: counts.__setitem__("init", counts["init"] + 1),
        nvmlShutdown=lambda: counts.__setitem__("shutdown", counts["shutdown"] + 1),
        nvmlDeviceGetCount=lambda: 1,
        nvmlDeviceGetHandleByIndex=lambda _i: handle,
        nvmlDeviceGetName=lambda _h: "FakeNV",
        nvmlDeviceGetUtilizationRates=lambda _h: SimpleNamespace(gpu=40),
        nvmlDeviceGetMemoryInfo=lambda _h: SimpleNamespace(
            total=2 * 1024 * 1024 * 1024,
            used=512 * 1024 * 1024,
        ),
        nvmlDeviceGetTemperature=lambda _h, _t: 61,
    )
    monkeypatch.setitem(sys.modules, "pynvml", fake)

    first = gpu_mod._get_gpu_info_pynvml()
    second = gpu_mod._get_gpu_info_pynvml()

    assert counts["init"] == 1
    assert counts["shutdown"] == 0
    assert first is not None
    assert first[0]["name"] == "FakeNV"
    assert first[0]["load"] == 40.0
    assert first[0]["backend"] == "pynvml"
    assert second == first
