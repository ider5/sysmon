"""Tests for GPU collector backends."""

from __future__ import annotations

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
