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
        from sysmon.collectors.registry import collect

        modules = self._config.modules
        with self._lock:
            prev = dict(self._snapshot)

        data: dict[str, Any] = {"timestamp": time.time()}

        keys: list[str] = []
        if modules.cpu:
            keys.append("cpu")
        if modules.memory:
            keys.append("memory")
        if modules.network:
            keys.append("network")
        if modules.disk:
            keys.append("disk")
        if modules.gpu and self._include_gpu and self._config.enable_gpu:
            keys.append("gpu")
        if modules.process:
            keys.append("process")

        for key in keys:
            self._safe_collect(data, prev, key, lambda n=key: collect(n, self._config))

        with self._lock:
            self._snapshot = data
