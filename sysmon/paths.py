"""Shared filesystem paths for sysmon."""

from pathlib import Path


def get_log_dir() -> Path:
    """Return the sysmon log directory, creating it if needed."""
    log_dir = Path.home() / ".sysmon"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_config_dir() -> Path:
    """Return the sysmon config directory."""
    return Path.home() / ".config" / "sysmon"


def get_config_path() -> Path:
    """Return the path to the sysmon config file."""
    return get_config_dir() / "config.toml"
