"""Background collector service with cached snapshots."""

from __future__ import annotations

import copy
import threading
import time
from typing import Any, Callable

from sysmon.config import SysmonConfig, load_config


class CollectorService:
    """Collect metrics on a background thread for non-blocking UI reads."""

    def __init__(
        self,
        interval: float = 1.0,
        include_gpu: bool = True,
        config: SysmonConfig | None = None,
    ) -> None:
        self._interval = interval
        self._include_gpu = include_gpu
        self._config = config or load_config()
        self._lock = threading.Lock()
        self._snapshot: dict[str, Any] = {}
        self._thread: threading.Thread | None = None
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start background collection."""
        if self._running:
            return
        try:
            self._collect_once()
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        except Exception:
            self._running = False
            self._thread = None
            raise

    def stop(self) -> None:
        """Stop background collection."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self._interval * 2)
            self._thread = None

    def get_snapshot(self) -> dict[str, Any]:
        """Return a copy of the latest cached snapshot."""
        with self._lock:
            return copy.deepcopy(self._snapshot)

    def get(self, key: str, default: Any = None) -> Any:
        """Return a single cached metric by key."""
        with self._lock:
            return copy.deepcopy(self._snapshot.get(key, default))

    def _loop(self) -> None:
        while self._running:
            time.sleep(self._interval)
            if self._running:
                self._collect_once()

    def _safe_collect(
        self,
        data: dict[str, Any],
        prev: dict[str, Any],
        key: str,
        collector: Callable[[], Any],
    ) -> None:
        try:
            data[key] = collector()
        except Exception as exc:
            errors = data.setdefault("errors", {})
            errors[key] = str(exc)
            if key in prev:
                data[key] = prev[key]

    def _collect_once(self) -> None:
        from sysmon.collectors.cpu import get_cpu_snapshot
        from sysmon.collectors.disk import get_disk_info
        from sysmon.collectors.gpu import get_gpu_info
        from sysmon.collectors.memory import get_memory_info
        from sysmon.collectors.network import get_network_info
        from sysmon.collectors.process import get_top_processes

        modules = self._config.modules
        with self._lock:
            prev = dict(self._snapshot)

        data: dict[str, Any] = {"timestamp": time.time()}

        if modules.cpu:
            self._safe_collect(data, prev, "cpu", get_cpu_snapshot)
        if modules.memory:
            self._safe_collect(data, prev, "memory", get_memory_info)
        if modules.network:
            self._safe_collect(
                data,
                prev,
                "network",
                lambda: get_network_info(self._config.network_interfaces),
            )
        if modules.disk:
            self._safe_collect(
                data,
                prev,
                "disk",
                lambda: get_disk_info(self._config.disk_mounts),
            )
        if modules.gpu and self._include_gpu and self._config.enable_gpu:
            self._safe_collect(data, prev, "gpu", get_gpu_info)
        if modules.process:
            self._safe_collect(
                data,
                prev,
                "process",
                lambda: get_top_processes(limit=self._config.process_limit),
            )

        with self._lock:
            self._snapshot = data
