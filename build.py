"""Build script for packaging sysmon as a standalone executable."""

import subprocess
import sys
from pathlib import Path

HIDDEN_IMPORTS = [
    "GPUtil",
    "shtab",
    "sysmon.display.title_worker",
    "sysmon.collectors.registry",
    "sysmon.collectors.cpu",
    "sysmon.collectors.memory",
    "sysmon.collectors.network",
    "sysmon.collectors.disk",
    "sysmon.collectors.gpu",
    "sysmon.collectors.process",
]

COLLECT_ALL = [
    "rich",
    "typer",
]


def build() -> None:
    """Build the executable using PyInstaller."""
    project_root = Path(__file__).parent.resolve()
    main_script = project_root / "sysmon" / "cli.py"
    exe_name = "sysmon.exe" if sys.platform == "win32" else "sysmon"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "sysmon",
        "--clean",
        "--paths",
        str(project_root),
        "--copy-metadata",
        "rich",
        "--copy-metadata",
        "typer",
    ]

    if sys.version_info < (3, 11):
        HIDDEN_IMPORTS.append("tomli")

    for hidden in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", hidden])

    for package in COLLECT_ALL:
        cmd.extend(["--collect-submodules", package])

    cmd.append(str(main_script))

    print("Building sysmon executable...")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=project_root, check=False)

    if result.returncode != 0:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(1)

    dist_dir = project_root / "dist"
    exe_path = dist_dir / exe_name

    if not exe_path.exists():
        print("\nBuild finished but executable was not found.")
        if dist_dir.exists():
            print("dist/ contents:")
            for item in dist_dir.iterdir():
                print(f"  {item.name}")
        sys.exit(1)

    if sys.platform != "win32":
        exe_path.chmod(exe_path.stat().st_mode | 0o111)

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print("\nBuild successful!")
    print(f"   Output: {exe_path}")
    print(f"   Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    build()
