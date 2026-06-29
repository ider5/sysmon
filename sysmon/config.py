"""Configuration loading for sysmon."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _load_toml(path: Path) -> dict[str, Any]:
    data = path.read_text(encoding="utf-8")
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    return tomllib.loads(data)


@dataclass(frozen=True)
class ModuleConfig:
    """Per-module visibility toggles."""

    cpu: bool = True
    memory: bool = True
    network: bool = True
    disk: bool = True
    gpu: bool = True
    process: bool = True


@dataclass(frozen=True)
class ThresholdConfig:
    """Alert thresholds for metrics (percent)."""

    cpu_warn: float = 80.0
    cpu_critical: float = 95.0
    memory_warn: float = 80.0
    memory_critical: float = 95.0
    disk_warn: float = 80.0
    disk_critical: float = 95.0


@dataclass(frozen=True)
class SysmonConfig:
    """Resolved sysmon settings."""

    refresh_interval: float = 1.0
    sample_interval: float = 1.0
    brief_refresh_interval: float = 2.0
    enable_gpu: bool = True
    default_format: str = "rich"
    modules: ModuleConfig = field(default_factory=ModuleConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    process_limit: int = 10

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> SysmonConfig:
        """Build config from a parsed TOML mapping."""
        modules_data = data.get("modules", {})
        thresholds_data = data.get("thresholds", {})

        modules = ModuleConfig(
            cpu=bool(modules_data.get("cpu", True)),
            memory=bool(modules_data.get("memory", True)),
            network=bool(modules_data.get("network", True)),
            disk=bool(modules_data.get("disk", True)),
            gpu=bool(modules_data.get("gpu", data.get("enable_gpu", True))),
            process=bool(modules_data.get("process", True)),
        )

        thresholds = ThresholdConfig(
            cpu_warn=float(thresholds_data.get("cpu_warn", 80.0)),
            cpu_critical=float(thresholds_data.get("cpu_critical", 95.0)),
            memory_warn=float(thresholds_data.get("memory_warn", 80.0)),
            memory_critical=float(thresholds_data.get("memory_critical", 95.0)),
            disk_warn=float(thresholds_data.get("disk_warn", 80.0)),
            disk_critical=float(thresholds_data.get("disk_critical", 95.0)),
        )

        return cls(
            refresh_interval=float(data.get("refresh_interval", 1.0)),
            sample_interval=float(data.get("sample_interval", 1.0)),
            brief_refresh_interval=float(
                data.get("brief_refresh_interval", data.get("refresh_interval", 2.0))
            ),
            enable_gpu=bool(data.get("enable_gpu", True)),
            default_format=str(data.get("default_format", "rich")),
            modules=modules,
            thresholds=thresholds,
            process_limit=int(data.get("process_limit", 10)),
        )


DEFAULT_CONFIG = SysmonConfig()

DEFAULT_CONFIG_TEMPLATE = """\
# SysMon configuration
# CLI flags override these values.

refresh_interval = 1.0
sample_interval = 1.0
brief_refresh_interval = 2.0
enable_gpu = true
default_format = "rich"
process_limit = 10

[modules]
cpu = true
memory = true
network = true
disk = true
gpu = true
process = true

[thresholds]
cpu_warn = 80
cpu_critical = 95
memory_warn = 80
memory_critical = 95
disk_warn = 80
disk_critical = 95
"""


def metric_status(
    percent: float,
    warn: float,
    critical: float,
) -> str:
    """Return ok, warn, or critical for a percentage value."""
    if percent >= critical:
        return "critical"
    if percent >= warn:
        return "warn"
    return "ok"


def load_config() -> SysmonConfig:
    """Load config from disk, falling back to defaults."""
    from sysmon.paths import get_config_path as config_path_fn

    path = config_path_fn()
    if not path.exists():
        return DEFAULT_CONFIG

    try:
        data = _load_toml(path)
    except Exception:
        return DEFAULT_CONFIG

    if not isinstance(data, dict):
        return DEFAULT_CONFIG

    return SysmonConfig.from_mapping(data)


def write_default_config() -> Path:
    """Write the default config file and return its path."""
    from sysmon.paths import get_config_path as config_path_fn

    path = config_path_fn()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
    return path
