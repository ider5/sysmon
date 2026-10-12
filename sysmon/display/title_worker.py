"""Background worker for terminal title mode."""

from __future__ import annotations

import argparse
import sys
import time
import traceback

from sysmon.collectors.memory import bytes_to_gb
from sysmon.collectors.network import format_speed
from sysmon.collectors.registry import collect
from sysmon.collectors.sensors import hottest_temperature
from sysmon.config import load_config
from sysmon.display.components import _finite_number, celsius
from sysmon.paths import get_log_dir

WORKER_MARKER = "sysmon.title_worker"
_MAX_CONSECUTIVE_ERRORS = 5


def sanitize_title(title: str) -> str:
    """Strip control characters that could break OSC title sequences."""
    return "".join(
        ch for ch in title if ch.isprintable() and ch not in "\x1b\x07"
    )


def osc_title_sequence(title: str) -> str:
    """Return a sanitized OSC 0 sequence for the terminal title."""
    return f"\033]0;{sanitize_title(title)}\007"


def _write_osc(payload: str) -> None:
    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        sys.stdout.write(payload)
        sys.stdout.flush()
        return
    if sys.platform != "win32":
        try:
            with open("/dev/tty", "w", encoding="utf-8") as tty:
                tty.write(payload)
                tty.flush()
                return
        except OSError:
            pass
    sys.stdout.write(payload)
    sys.stdout.flush()


def set_title(title: str) -> None:
    """Set terminal title via OSC (and Windows console API)."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleTitleW(sanitize_title(title))
        except Exception:
            pass
    _write_osc(osc_title_sequence(title))


def _num(info: object, key: str, default: float = 0.0) -> float:
    if not isinstance(info, dict):
        return default
    value = _finite_number(info.get(key))
    return default if value is None else value


def build_title(no_gpu: bool) -> str:
    """Build plain-text title string."""
    settings = load_config()
    parts: list[str] = []
    if settings.modules.cpu:
        cpu = collect("cpu", settings)
        cpu_part = f"CPU {_num(cpu, 'percent'):.0f}%"
        load_avg = cpu.get("load_avg") if isinstance(cpu, dict) else None
        logical = _num(cpu, "count_logical", 1.0) or 1.0
        if isinstance(load_avg, (list, tuple)) and load_avg:
            one = _finite_number(load_avg[0])
            if one is not None and one >= logical:
                cpu_part += f" LD {one:.2f}"
        parts.append(cpu_part)
    if settings.modules.memory:
        mem = collect("memory", settings)
        ram = (
            f"RAM {bytes_to_gb(_num(mem, 'used'))}/{bytes_to_gb(_num(mem, 'total'))}G "
            f"({_num(mem, 'percent'):.0f}%)"
        )
        swap_total = mem.get("swap_total") or 0
        swap_percent = mem.get("swap_percent") or 0
        if swap_total > 0 and swap_percent > 0:
            ram += f" SWAP {float(swap_percent):.0f}%"
        parts.append(ram)
    if settings.modules.network:
        net = collect("network", settings)
        parts.append(
            f"↑{format_speed(_num(net, 'speed_up'))} ↓{format_speed(_num(net, 'speed_down'))}"
        )
        errin = int(_num(net, "errin"))
        errout = int(_num(net, "errout"))
        dropin = int(_num(net, "dropin"))
        dropout = int(_num(net, "dropout"))
        if errin or errout or dropin or dropout:
            parts.append(f"ERR {errin}/{errout} DROP {dropin}/{dropout}")
    if settings.modules.disk:
        disk = collect("disk", settings)
        percent = disk.get("percent") if isinstance(disk, dict) else None
        if (
            isinstance(percent, (int, float))
            and not isinstance(percent, bool)
            and float(percent) >= settings.thresholds.disk_warn
        ):
            parts.append(f"DISK {float(percent):.0f}%")
    if settings.modules.gpu and settings.enable_gpu and not no_gpu:
        gpus = collect("gpu", settings)
        if gpus:
            gpu = gpus[0] if isinstance(gpus, list) and gpus and isinstance(gpus[0], dict) else None
            if gpu is None:
                gpu = {}
            gpu_str = (
                f"GPU {_num(gpu, 'load'):.0f}% "
                f"{_num(gpu, 'memory_used')/1024:.1f}/{_num(gpu, 'memory_total')/1024:.1f}G"
            )
            temp = celsius(gpu.get("temperature"))
            if temp is not None:
                gpu_str += f" {temp:g}°C"
            parts.append(gpu_str)
    if settings.modules.sensors:
        sensors = collect("sensors", settings)
        battery = sensors.get("battery") if isinstance(sensors, dict) else None
        if isinstance(battery, dict) and battery.get("percent") is not None:
            plugged = " AC" if battery.get("power_plugged") else ""
            parts.append(f"BAT {float(battery['percent']):.0f}%{plugged}")
        hottest = hottest_temperature(sensors) if isinstance(sensors, dict) else None
        if hottest is not None:
            parts.append(f"TEMP {hottest[0]:.0f}°C")
    if not parts:
        return "sysmon"
    return " │ ".join(parts)


def run_loop(refresh_rate: float, no_gpu: bool) -> None:
    """Main title update loop."""
    settings = load_config()
    if settings.modules.network:
        collect("network", settings)
    time.sleep(0.5)

    failures = 0
    while True:
        try:
            set_title(build_title(no_gpu))
            failures = 0
        except Exception:
            failures += 1
            log_path = get_log_dir() / "title_error.log"
            try:
                if log_path.exists() and log_path.stat().st_size > 256_000:
                    log_path.write_text("", encoding="utf-8")
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(
                        f"{time.strftime('%Y-%m-%d %H:%M:%S')}: "
                        f"{traceback.format_exc()}\n"
                    )
            except OSError:
                pass
            if failures >= _MAX_CONSECUTIVE_ERRORS:
                raise SystemExit(1)
        time.sleep(refresh_rate)


def main() -> None:
    parser = argparse.ArgumentParser(prog=WORKER_MARKER)
    parser.add_argument("--refresh", type=float, default=2.0)
    parser.add_argument("--no-gpu", action="store_true")
    parser.add_argument(
        "--marker",
        default=WORKER_MARKER,
        help="Identifies this process as a title worker.",
    )
    args = parser.parse_args()
    run_loop(args.refresh, args.no_gpu)


if __name__ == "__main__":
    main()
