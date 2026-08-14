"""GPU metrics collector.

Uses pynvml (NVIDIA official) when available, falls back to GPUtil.
AMD/Intel GPUs are not supported.
"""

from __future__ import annotations

import atexit
import threading
from typing import Optional, TypedDict

_nvml_state: bool | None = None
_nvml_lock = threading.Lock()


class GpuInfo(TypedDict):
    """Normalized GPU metrics payload."""

    id: int
    name: str
    load: float
    memory_total: float
    memory_used: float
    temperature: float | None
    backend: str


def reset_nvml_state_for_tests() -> None:
    """Reset NVML init cache (tests only)."""
    global _nvml_state
    with _nvml_lock:
        _nvml_state = None


def _shutdown_nvml() -> None:
    global _nvml_state
    try:
        import pynvml

        pynvml.nvmlShutdown()
    except Exception:
        pass
    with _nvml_lock:
        _nvml_state = None


def _ensure_nvml() -> bool:
    global _nvml_state
    with _nvml_lock:
        if _nvml_state is not None:
            return _nvml_state
        try:
            import pynvml

            pynvml.nvmlInit()
            atexit.register(_shutdown_nvml)
            _nvml_state = True
            return True
        except Exception:
            _nvml_state = False
            return False


def _get_gpu_info_pynvml() -> Optional[list[GpuInfo]]:
    if not _ensure_nvml():
        return None
    try:
        import pynvml

        count = pynvml.nvmlDeviceGetCount()
        if count == 0:
            return None

        gpus: list[GpuInfo] = []
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")

            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            try:
                temp = pynvml.nvmlDeviceGetTemperature(
                    handle, pynvml.NVML_TEMPERATURE_GPU
                )
            except Exception:
                temp = None

            gpus.append(
                {
                    "id": i,
                    "name": name,
                    "load": float(util.gpu),
                    "memory_total": mem.total / (1024 * 1024),
                    "memory_used": mem.used / (1024 * 1024),
                    "temperature": temp,
                    "backend": "pynvml",
                }
            )
        return gpus
    except Exception:
        return None


def _get_gpu_info_gputil() -> Optional[list[GpuInfo]]:
    try:
        import GPUtil

        gpus = GPUtil.getGPUs()
        if not gpus:
            return None

        return [
            {
                "id": gpu.id,
                "name": gpu.name,
                "load": gpu.load * 100,
                "memory_total": gpu.memoryTotal,
                "memory_used": gpu.memoryUsed,
                "temperature": gpu.temperature,
                "backend": "gputil",
            }
            for gpu in gpus
        ]
    except Exception:
        return None


def get_gpu_info() -> Optional[list[GpuInfo]]:
    """Get GPU metrics if available (NVIDIA only)."""
    return _get_gpu_info_pynvml() or _get_gpu_info_gputil()
