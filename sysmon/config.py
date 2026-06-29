"""Configuration loading for sysmon."""

from __future__ import annotations

from dataclasses import dataclass
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
class SysmonConfig:
    """Resolved sysmon settings."""

    refresh_interval: float = 1.0
    sample_interval: float = 1.0
    brief_refresh_interval: float = 2.0
    enable_gpu: bool = True
    default_format: str = "rich"

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> SysmonConfig:
        """Build config from a parsed TOML mapping."""
        return cls(
            refresh_interval=float(data.get("refresh_interval", 1.0)),
            sample_interval=float(data.get("sample_interval", 1.0)),
            brief_refresh_interval=float(
                data.get("brief_refresh_interval", data.get("refresh_interval", 2.0))
            ),
            enable_gpu=bool(data.get("enable_gpu", True)),
            default_format=str(data.get("default_format", "rich")),
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
"""


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
