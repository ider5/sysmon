"""Brief single-line display mode."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Iterable

import psutil
from rich.console import Console
from rich.live import Live
from rich.text import Text

from sysmon.collectors.memory import bytes_to_gb
from sysmon.collectors.network import format_speed
from sysmon.collectors.registry import collect
from sysmon.collectors.sensors import hottest_temperature
from sysmon.config import ThresholdConfig, load_config, metric_status
from sysmon.display.components import celsius
from sysmon.display.title_worker import WORKER_MARKER

_STATUS_COLORS = {
    "ok": "green",
    "warn": "yellow",
    "critical": "red",
}


def _threshold_color(percent: float, warn: float, critical: float) -> str:
    """Map a percentage to the dashboard threshold color."""
    return _STATUS_COLORS[metric_status(percent, warn, critical)]


_PID_FILE = Path.home() / ".sysmon_title.pid"
_LOCK_FILE = Path.home() / ".sysmon_title.lock"
_WORKER_START_GRACE = 0.2


def _format_cpu(
    info: dict,
    no_color: bool = False,
    warn: float = 80.0,
    critical: float = 95.0,
) -> Text:
    """Format CPU info as compact text."""
    text = Text()
    text.append("CPU ")
    pct = info["percent"]
    if no_color:
        text.append(f"{pct:.0f}%")
    else:
        text.append(f"{pct:.0f}%", style=_threshold_color(pct, warn, critical))

    if info["freq_current"]:
        text.append(f" {info['freq_current']:.0f}M")
    return text


def _format_memory(
    info: dict,
    no_color: bool = False,
    warn: float = 80.0,
    critical: float = 95.0,
) -> Text:
    """Format memory info as compact text."""
    text = Text()
    text.append("RAM ")
    used = bytes_to_gb(info["used"])
    total = bytes_to_gb(info["total"])
    pct = info["percent"]

    if no_color:
        text.append(f"{used}/{total}G ({pct:.0f}%)")
    else:
        text.append(f"{used}/{total}G", style="bold")
        text.append(f" ({pct:.0f}%)", style=_threshold_color(pct, warn, critical))
    swap_total = info.get("swap_total") or 0
    swap_percent = info.get("swap_percent") or 0
    if swap_total > 0 and swap_percent > 0:
        text.append(" SWAP ")
        swap_label = f"{float(swap_percent):.0f}%"
        if no_color:
            text.append(swap_label)
        else:
            text.append(swap_label, style=_threshold_color(float(swap_percent), warn, critical))
    return text


def _format_network(info: dict, no_color: bool = False) -> Text:
    """Format network info as compact text."""
    text = Text()
    if no_color:
        text.append(f"↑{format_speed(info['speed_up'])} ↓{format_speed(info['speed_down'])}")
    else:
        text.append("↑", style="green")
        text.append(format_speed(info["speed_up"]), style="green")
        text.append(" ↓", style="cyan")
        text.append(format_speed(info["speed_down"]), style="cyan")
    return text


def _format_gpu(
    gpus: list | None,
    no_color: bool = False,
    warn: float = 80.0,
    critical: float = 95.0,
) -> Text | None:
    """Format GPU info as compact text."""
    if not gpus:
        return None

    gpu = gpus[0]
    text = Text()
    text.append("GPU ")

    load = gpu["load"]
    if no_color:
        text.append(f"{load:.0f}%")
    else:
        text.append(f"{load:.0f}%", style=_threshold_color(load, warn, critical))

    mem_used = gpu["memory_used"] / 1024
    mem_total = gpu["memory_total"] / 1024
    text.append(f" {mem_used:.1f}/{mem_total:.1f}G")

    temp = celsius(gpu.get("temperature"))
    if temp is not None:
        if no_color:
            text.append(f" {temp:g}°C")
        else:
            color = "green" if temp < 65 else "yellow" if temp < 80 else "red"
            text.append(f" {temp:g}°C", style=color)

    return text


def _temperature_color(current: float, entry: dict) -> str:
    critical = entry.get("critical")
    high = entry.get("high")
    if isinstance(critical, (int, float)) and not isinstance(critical, bool) and current >= critical:
        return "red"
    if isinstance(high, (int, float)) and not isinstance(high, bool) and current >= high:
        return "yellow"
    return "bold"


def _format_sensors(info: dict, no_color: bool = False) -> Text | None:
    """Format battery charge and the hottest temperature for the compact line."""
    pieces: list[Text] = []
    battery = info.get("battery") if isinstance(info, dict) else None
    if isinstance(battery, dict) and battery.get("percent") is not None:
        text = Text()
        text.append("BAT ")
        percent = f"{float(battery['percent']):.0f}%"
        if no_color:
            text.append(percent)
        else:
            text.append(percent, style="bold")
        if battery.get("power_plugged"):
            text.append(" AC")
        pieces.append(text)

    hottest = hottest_temperature(info) if isinstance(info, dict) else None
    if hottest is not None:
        current, entry = hottest
        text = Text()
        text.append("TEMP ")
        label = f"{current:.0f}°C"
        if no_color:
            text.append(label)
        else:
            text.append(label, style=_temperature_color(current, entry))
        pieces.append(text)

    if not pieces:
        return None
    line = Text()
    for index, piece in enumerate(pieces):
        if index:
            line.append(" │ ", style="dim")
        line.append_text(piece)
    return line


def build_brief_line(
    no_color: bool = False,
    no_gpu: bool = False,
    interfaces: Iterable[str] | None = None,
    thresholds: ThresholdConfig | None = None,
) -> Text:
    """Build a single line with all key metrics."""
    if thresholds is None:
        thresholds = load_config().thresholds

    settings = load_config()
    if interfaces is not None:
        settings = replace(settings, network_interfaces=tuple(interfaces))

    parts: list[Text] = []
    if settings.modules.cpu:
        parts.append(
            _format_cpu(
                collect("cpu", settings),
                no_color,
                warn=thresholds.cpu_warn,
                critical=thresholds.cpu_critical,
            )
        )
    if settings.modules.memory:
        parts.append(
            _format_memory(
                collect("memory", settings),
                no_color,
                warn=thresholds.memory_warn,
                critical=thresholds.memory_critical,
            )
        )
    if settings.modules.network:
        parts.append(_format_network(collect("network", settings), no_color))
    if settings.modules.gpu and settings.enable_gpu and not no_gpu:
        gpu_text = _format_gpu(
            collect("gpu", settings),
            no_color,
            warn=thresholds.gpu_warn,
            critical=thresholds.gpu_critical,
        )
        if gpu_text:
            parts.append(gpu_text)
    if settings.modules.sensors:
        sensor_text = _format_sensors(collect("sensors", settings), no_color)
        if sensor_text:
            parts.append(sensor_text)

    line = Text()
    if not parts:
        line.append("modules disabled", style=None if no_color else "dim")
        return line
    for index, part in enumerate(parts):
        if index:
            line.append(" │ ", style="dim")
        line.append_text(part)
    return line


def print_brief(
    console: Console,
    no_color: bool = False,
    no_gpu: bool = False,
    sample_interval: float = 1.0,
    interfaces: Iterable[str] | None = None,
    thresholds: ThresholdConfig | None = None,
) -> None:
    """Print a single line of key metrics."""
    settings = load_config()
    if interfaces is not None:
        settings = replace(settings, network_interfaces=tuple(interfaces))
    if settings.modules.network:
        collect("network", settings)
    time.sleep(sample_interval)
    console.print(
        build_brief_line(
            no_color, no_gpu, interfaces=interfaces, thresholds=thresholds
        )
    )


def run_brief_watch(
    console: Console,
    refresh_rate: float = 1.0,
    no_color: bool = False,
    no_gpu: bool = False,
    interfaces: Iterable[str] | None = None,
    thresholds: ThresholdConfig | None = None,
) -> None:
    """Run brief display in watch mode."""
    settings = load_config()
    if interfaces is not None:
        settings = replace(settings, network_interfaces=tuple(interfaces))
    if settings.modules.network:
        collect("network", settings)
    time.sleep(min(0.5, refresh_rate))

    with Live(
        build_brief_line(
            no_color, no_gpu, interfaces=interfaces, thresholds=thresholds
        ),
        console=console,
        refresh_per_second=4,
        transient=False,
    ) as live:
        try:
            while True:
                time.sleep(refresh_rate)
                try:
                    live.update(
                        build_brief_line(
                            no_color,
                            no_gpu,
                            interfaces=interfaces,
                            thresholds=thresholds,
                        )
                    )
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    live.update(Text(f"brief error: {exc}", style="red"))
        except KeyboardInterrupt:
            pass


def _is_title_worker_process(proc: psutil.Process) -> bool:
    """Return True if process is a sysmon title worker."""
    try:
        cmdline = " ".join(proc.cmdline())
        return WORKER_MARKER in cmdline or "title_worker" in cmdline
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def _write_pid_file(pid: int) -> None:
    """Atomically write PID file."""
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = _PID_FILE.with_suffix(".tmp")
    temp.write_text(str(pid), encoding="utf-8")
    temp.replace(_PID_FILE)


def _acquire_title_lock():
    """Try to lock title-mode start/stop. Returns a file handle or None."""
    _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle = open(_LOCK_FILE, "a+", encoding="utf-8")
    try:
        handle.write(" ")
        handle.flush()
        handle.seek(0)
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def _release_title_lock(handle) -> None:
    if handle is None:
        return
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    handle.close()


def _stop_existing_title_process() -> None:
    """Stop existing title process if running."""
    if not _PID_FILE.exists():
        return

    try:
        pid = int(_PID_FILE.read_text(encoding="utf-8").strip())
        if psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            if _is_title_worker_process(proc):
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, OSError):
        pass
    finally:
        _PID_FILE.unlink(missing_ok=True)


def title_worker_command(refresh_rate: float, no_gpu: bool) -> list[str]:
    """Build the argv used to spawn the title worker."""
    if getattr(sys, "frozen", False):
        cmd = [
            sys.executable,
            "--title-worker",
            "--title-refresh",
            str(refresh_rate),
        ]
        if no_gpu:
            cmd.append("--title-no-gpu")
        return cmd
    cmd = [
        sys.executable,
        "-m",
        "sysmon.display.title_worker",
        "--refresh",
        str(refresh_rate),
        "--marker",
        WORKER_MARKER,
    ]
    if no_gpu:
        cmd.append("--no-gpu")
    return cmd


def run_title_mode(
    console: Console,
    refresh_rate: float = 2.0,
    no_gpu: bool = False,
) -> None:
    """Run in terminal title mode - non-blocking background worker."""
    lock = _acquire_title_lock()
    if lock is None:
        console.print("[yellow]Title mode start is already in progress.[/yellow]")
        return

    proc = None
    try:
        _stop_existing_title_process()
        cmd = title_worker_command(refresh_rate, no_gpu)
        proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL)
        time.sleep(_WORKER_START_GRACE)
        if proc.poll() is not None:
            _PID_FILE.unlink(missing_ok=True)
            console.print("[red]Title mode worker exited immediately.[/red]")
            return

        _write_pid_file(proc.pid)

        console.print(f"[green]✓[/green] Title mode started (PID: {proc.pid})")
        console.print("[dim]System info will appear in terminal title bar.[/dim]")
        console.print("[dim]To stop: sysmon brief --stop[/dim]")

        import os

        if os.environ.get("TERM_PROGRAM") == "vscode":
            console.print()
            console.print("[yellow]⚠[/yellow] VS Code terminal may not show title updates.")
            console.print(
                "[dim]For best results, use Windows Terminal or other standard terminal.[/dim]"
            )
    except Exception as e:
        if proc is not None and proc.poll() is None:
            proc.terminate()
        console.print(f"[red]Error starting title mode: {e}[/red]")
    finally:
        _release_title_lock(lock)


def stop_title_mode(console: Console) -> None:
    """Stop the background title process."""
    lock = _acquire_title_lock()
    if lock is None:
        console.print("[yellow]Title mode is busy. Try again.[/yellow]")
        return

    try:
        if not _PID_FILE.exists():
            console.print("[dim]Title mode is not running.[/dim]")
            return

        try:
            pid = int(_PID_FILE.read_text(encoding="utf-8").strip())
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                if _is_title_worker_process(proc):
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    console.print(f"[green]✓[/green] Title mode stopped (PID: {pid})")
                else:
                    console.print("[dim]PID file did not match a title worker.[/dim]")
            else:
                console.print("[dim]Title mode process was not running.[/dim]")
        except Exception as e:
            console.print(f"[red]Error stopping title mode: {e}[/red]")
        finally:
            _PID_FILE.unlink(missing_ok=True)
    finally:
        _release_title_lock(lock)
