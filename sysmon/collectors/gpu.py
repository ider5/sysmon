"""GPU metrics collector.

Uses GPUtil for NVIDIA GPU monitoring. Gracefully falls back when no GPU is available.
"""

from typing import Optional


def get_gpu_info() -> Optional[list[dict]]:
    """Get GPU metrics if available.

    Returns:
        List of dicts with keys: id, name, load, memory_total, memory_used, temperature
        Returns None if no GPU or GPUtil not available.
    """
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if not gpus:
            return None

        return [
            {
                "id": gpu.id,
                "name": gpu.name,
                "load": gpu.load * 100,  # Convert 0-1 to percentage
                "memory_total": gpu.memoryTotal,
                "memory_used": gpu.memoryUsed,
                "temperature": gpu.temperature,
            }
            for gpu in gpus
        ]
    except Exception:
        return None
