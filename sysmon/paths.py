"""Shared filesystem paths for sysmon."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_log_dir() -> Path:
    """Return the sysmon log directory, creating it if needed."""
    log_dir = Path.home() / ".sysmon"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _platform_config_dir() -> Path:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "sysmon"
        return Path.home() / "AppData" / "Roaming" / "sysmon"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "sysmon"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "sysmon"
    return Path.home() / ".config" / "sysmon"


def get_config_dir() -> Path:
    """Return the sysmon config directory for this platform."""
    preferred = _platform_config_dir()
    if (preferred / "config.toml").exists():
        return preferred
    if sys.platform in ("win32", "darwin"):
        legacy = Path.home() / ".config" / "sysmon"
        if (legacy / "config.toml").exists():
            return legacy
    return preferred


def get_config_path() -> Path:
    """Return the path to the sysmon config file."""
    return get_config_dir() / "config.toml"
