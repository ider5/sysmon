"""Tests for configuration loading."""

from pathlib import Path

from sysmon.config import (
    SysmonConfig,
    clear_config_cache,
    load_config,
    write_default_config,
)


def test_default_config_values():
    config = SysmonConfig()
    assert config.refresh_interval == 1.0
    assert config.sample_interval == 1.0
    assert config.brief_refresh_interval == 2.0
    assert config.enable_gpu is True
    assert config.default_format == "rich"


def test_from_mapping():
    config = SysmonConfig.from_mapping(
        {
            "refresh_interval": 3.0,
            "sample_interval": 0.5,
            "brief_refresh_interval": 4.0,
            "enable_gpu": False,
            "default_format": "json",
        }
    )
    assert config.refresh_interval == 3.0
    assert config.sample_interval == 0.5
    assert config.brief_refresh_interval == 4.0
    assert config.enable_gpu is False
    assert config.default_format == "json"


def test_metric_status():
    from sysmon.config import metric_status

    assert metric_status(50, 80, 95) == "ok"
    assert metric_status(85, 80, 95) == "warn"
    assert metric_status(99, 80, 95) == "critical"


def test_from_mapping_modules_and_thresholds():
    config = SysmonConfig.from_mapping(
        {
            "modules": {"cpu": False, "process": True},
            "thresholds": {"cpu_warn": 70, "cpu_critical": 90},
            "process_limit": 5,
        }
    )
    assert config.modules.cpu is False
    assert config.modules.process is True
    assert config.thresholds.cpu_warn == 70.0
    assert config.process_limit == 5


def test_from_mapping_disk_and_network_selection():
    config = SysmonConfig.from_mapping(
        {
            "disk_mounts": ["C:\\", "D:\\"],
            "network_interfaces": ["eth0", "Wi-Fi"],
        }
    )
    assert config.disk_mounts == ("C:\\", "D:\\")
    assert config.network_interfaces == ("eth0", "Wi-Fi")


def test_load_config_from_file(tmp_path: Path, monkeypatch):
    clear_config_cache()
    config_dir = tmp_path / ".config" / "sysmon"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(
        'refresh_interval = 2.5\nsample_interval = 0.2\nenable_gpu = false\n',
        encoding="utf-8",
    )

    monkeypatch.setattr("sysmon.paths.get_config_path", lambda: config_path)
    config = load_config()

    assert config.refresh_interval == 2.5
    assert config.sample_interval == 0.2
    assert config.enable_gpu is False


def test_load_config_caches_by_mtime(tmp_path: Path, monkeypatch):
    clear_config_cache()
    config_path = tmp_path / "config.toml"
    config_path.write_text("refresh_interval = 1.5\n", encoding="utf-8")
    monkeypatch.setattr("sysmon.paths.get_config_path", lambda: config_path)

    first = load_config()
    second = load_config()
    assert first is second
    assert first.refresh_interval == 1.5

    config_path.write_text("refresh_interval = 3.5\n", encoding="utf-8")
    # Ensure mtime advances on fast filesystems
    import os
    import time

    os.utime(config_path, (time.time() + 1, time.time() + 1))
    third = load_config()
    assert third is not first
    assert third.refresh_interval == 3.5


def test_load_config_invalid_toml_falls_back(tmp_path: Path, monkeypatch):
    clear_config_cache()
    config_path = tmp_path / "config.toml"
    config_path.write_text("not = [valid\n", encoding="utf-8")
    monkeypatch.setattr("sysmon.paths.get_config_path", lambda: config_path)

    config = load_config()
    assert config.refresh_interval == 1.0
    assert config.enable_gpu is True


def test_write_default_config(tmp_path: Path, monkeypatch):
    clear_config_cache()
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("sysmon.paths.get_config_path", lambda: config_path)

    written = write_default_config()

    assert written == config_path
    assert config_path.exists()
    assert "refresh_interval" in config_path.read_text(encoding="utf-8")
