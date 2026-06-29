"""Build script for packaging sysmon as a standalone executable."""

import subprocess
import sys
from pathlib import Path


def build():
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
        str(main_script),
    ]

    print("Building sysmon executable...")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=project_root)

    if result.returncode == 0:
        dist_dir = project_root / "dist"
        exe_path = dist_dir / exe_name
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("\nBuild successful!")
            print(f"   Output: {exe_path}")
            print(f"   Size: {size_mb:.1f} MB")
        else:
            print(f"\nBuild completed. Check {dist_dir} for output.")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    build()
