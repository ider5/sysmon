"""GPU metrics collector.

Uses pynvml (NVIDIA official) when available, falls back to GPUtil.
AMD/Intel GPUs are not supported.
"""

from __future__ import annotations

from typing import Optional, TypedDict


class GpuInfo(TypedDict):
    """Normalized GPU metrics payload."""

    id: int
    name: str
    load: float
    memory_total: float
    memory_used: float
    temperature: float | None
    backend: str


def _get_gpu_info_pynvml() -> Optional[list[GpuInfo]]:
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
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
        finally:
            pynvml.nvmlShutdown()
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
