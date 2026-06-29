"""Background worker for terminal title mode."""

import argparse
import ctypes
import sys
import time
import traceback

from sysmon.collectors.cpu import get_cpu_info
from sysmon.collectors.gpu import get_gpu_info
from sysmon.collectors.memory import bytes_to_gb, get_memory_info
from sysmon.collectors.network import format_speed, get_network_info
from sysmon.paths import get_log_dir

WORKER_MARKER = "sysmon.title_worker"


def set_title(title: str) -> None:
    """Set terminal title using platform-specific method."""
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    else:
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()


def build_title(no_gpu: bool) -> str:
    """Build plain-text title string."""
    cpu = get_cpu_info()
    mem = get_memory_info()
    net = get_network_info()

    parts = [
        f"CPU {cpu['percent']:.0f}%",
        (
            f"RAM {bytes_to_gb(mem['used'])}/{bytes_to_gb(mem['total'])}G "
            f"({mem['percent']:.0f}%)"
        ),
        f"↑{format_speed(net['speed_up'])} ↓{format_speed(net['speed_down'])}",
    ]

    if not no_gpu:
        gpus = get_gpu_info()
        if gpus:
            gpu = gpus[0]
            gpu_str = (
                f"GPU {gpu['load']:.0f}% "
                f"{gpu['memory_used']/1024:.1f}/{gpu['memory_total']/1024:.1f}G"
            )
            if gpu["temperature"]:
                gpu_str += f" {gpu['temperature']}°C"
            parts.append(gpu_str)

    return " │ ".join(parts)


def run_loop(refresh_rate: float, no_gpu: bool) -> None:
    """Main title update loop."""
    get_network_info()
    time.sleep(0.5)

    while True:
        try:
            set_title(build_title(no_gpu))
        except Exception:
            log_path = get_log_dir() / "title_error.log"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}: {traceback.format_exc()}\n")
        time.sleep(refresh_rate)


def main() -> None:
    parser = argparse.ArgumentParser(prog=WORKER_MARKER)
    parser.add_argument("--refresh", type=float, default=2.0)
    parser.add_argument("--no-gpu", action="store_true")
    args = parser.parse_args()
    run_loop(args.refresh, args.no_gpu)


if __name__ == "__main__":
    main()
