"""Background collector service with cached snapshots."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from sysmon.config import SysmonConfig, load_config


class CollectorService:
    """Collect metrics on a background thread for non-blocking UI reads."""

    def __init__(
        self,
        interval: float = 1.0,
        include_gpu: bool = True,
        include_sensors: bool | None = None,
        config: SysmonConfig | None = None,
    ) -> None:
        self._interval = interval
        self._include_gpu = include_gpu
        self._include_sensors = include_sensors
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
        """Return a shallow copy of the latest cached snapshot."""
        with self._lock:
            return dict(self._snapshot)

    def get(self, key: str, default: Any = None) -> Any:
        """Return a single cached metric by key."""
        with self._lock:
            return self._snapshot.get(key, default)

    def _loop(self) -> None:
        while self._running:
            time.sleep(self._interval)
            if self._running:
                self._collect_once()

    def _enabled_keys(self) -> list[str]:
        modules = self._config.modules
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
        sensors_enabled = (
            modules.sensors if self._include_sensors is None else self._include_sensors
        )
        if sensors_enabled:
            keys.append("sensors")
        return keys

    def _collect_once(self) -> None:
        from sysmon.collectors.registry import collect

        with self._lock:
            prev = dict(self._snapshot)

        data: dict[str, Any] = {"timestamp": time.time()}
        keys = self._enabled_keys()
        if not keys:
            with self._lock:
                self._snapshot = data
            return

        def _run(key: str) -> tuple[str, Any]:
            return key, collect(key, self._config)

        with ThreadPoolExecutor(max_workers=len(keys)) as pool:
            futures = {pool.submit(_run, key): key for key in keys}
            for fut in as_completed(futures):
                key = futures[fut]
                try:
                    name, value = fut.result()
                    data[name] = value
                except Exception as exc:
                    errors = data.setdefault("errors", {})
                    errors[key] = str(exc)
                    if key in prev:
                        data[key] = prev[key]

        with self._lock:
            self._snapshot = data
