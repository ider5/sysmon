"""Tests for platform-specific config paths."""

from pathlib import Path

from sysmon import paths


def test_config_dir_windows_uses_appdata(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\me\AppData\Roaming")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: Path("C:/Users/me")))
    monkeypatch.setattr(paths.Path, "exists", lambda self: False)
    assert paths.get_config_dir() == Path(r"C:\Users\me\AppData\Roaming") / "sysmon"


def test_config_dir_macos_uses_application_support(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: Path("/Users/me")))
    monkeypatch.setattr(paths.Path, "exists", lambda self: False)
    assert paths.get_config_dir() == Path("/Users/me/Library/Application Support/sysmon")


def test_config_dir_linux_uses_xdg_or_dotconfig(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: Path("/home/me")))
    monkeypatch.setattr(paths.Path, "exists", lambda self: False)
    assert paths.get_config_dir() == Path("/home/me/.config/sysmon")


def test_config_dir_prefers_legacy_if_present(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    home = tmp_path / "home"
    legacy = home / ".config" / "sysmon"
    legacy.mkdir(parents=True)
    (legacy / "config.toml").write_text("refresh_interval = 1.0\n", encoding="utf-8")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: home))
    assert paths.get_config_dir() == legacy
