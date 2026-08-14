"""Guards for packaging layout that affect PyPI and binary builds."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib


def _load_pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def test_repo_root_does_not_shadow_pep517_build():
    """A root-level build.py would shadow `python -m build` in publish CI."""
    assert not (ROOT / "build.py").exists()
    assert (ROOT / "scripts" / "build_exe.py").exists()


def test_dev_extra_is_tooling_only():
    extras = _load_pyproject()["project"]["optional-dependencies"]
    assert extras["dev"] == [
        "pyinstaller>=6.0.0",
        "pytest>=7.0",
        "ruff>=0.4",
        "shtab>=1.7",
    ]
    assert "GPUtil>=1.4.0" in extras["gpu"]
    assert "nvidia-ml-py>=12.0.0" in extras["gpu"]


def test_project_urls_and_classifiers():
    project = _load_pyproject()["project"]
    assert project["urls"] == {
        "Homepage": "https://github.com/ider5/sysmon",
        "Repository": "https://github.com/ider5/sysmon",
        "Changelog": "https://github.com/ider5/sysmon/blob/master/CHANGELOG.md",
    }
    required = [
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "License :: OSI Approved :: MIT License",
        "Topic :: System :: Monitoring",
    ]
    for classifier in required:
        assert classifier in project["classifiers"]


def test_setuptools_finds_sysmon_packages():
    find = _load_pyproject()["tool"]["setuptools"]["packages"]["find"]
    assert find["include"] == ["sysmon*"]
