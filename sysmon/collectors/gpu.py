"""GPU metrics collector.

Uses pynvml (NVIDIA official) when available, falls back to GPUtil.
AMD/Intel GPUs are not supported.
"""

from typing import Optional


def _get_gpu_info_pynvml() -> Optional[list[dict]]:
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            count = pynvml.nvmlDeviceGetCount()
            if count == 0:
                return None

            gpus = []
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


def _get_gpu_info_gputil() -> Optional[list[dict]]:
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


def get_gpu_info() -> Optional[list[dict]]:
    """Get GPU metrics if available (NVIDIA only)."""
    return _get_gpu_info_pynvml() or _get_gpu_info_gputil()
