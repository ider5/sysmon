"""Guards for packaging layout that affect PyPI and binary builds."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_repo_root_does_not_shadow_pep517_build():
    """A root-level build.py would shadow `python -m build` in publish CI."""
    assert not (ROOT / "build.py").exists()
    assert (ROOT / "scripts" / "build_exe.py").exists()
