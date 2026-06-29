"""Tests for configuration loading."""

from pathlib import Path

from sysmon.config import SysmonConfig, load_config, write_default_config


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


def test_load_config_from_file(tmp_path: Path, monkeypatch):
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


def test_write_default_config(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config.toml"
    monkeypatch.setattr("sysmon.paths.get_config_path", lambda: config_path)

    written = write_default_config()

    assert written == config_path
    assert config_path.exists()
    assert "refresh_interval" in config_path.read_text(encoding="utf-8")
