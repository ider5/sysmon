"""Brief single-line display mode."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import psutil
from rich.console import Console
from rich.live import Live
from rich.text import Text

from sysmon.collectors.cpu import get_cpu_info
from sysmon.collectors.gpu import get_gpu_info
from sysmon.collectors.memory import bytes_to_gb, get_memory_info
from sysmon.collectors.network import format_speed, get_network_info
from sysmon.display.title_worker import WORKER_MARKER

_PID_FILE = Path.home() / ".sysmon_title.pid"


def _format_cpu(info: dict, no_color: bool = False) -> Text:
    """Format CPU info as compact text."""
    text = Text()
    text.append("CPU ")
    pct = info["percent"]
    if no_color:
        text.append(f"{pct:.0f}%")
    else:
        color = "green" if pct < 60 else "yellow" if pct < 80 else "red"
        text.append(f"{pct:.0f}%", style=color)

    if info["freq_current"]:
        text.append(f" {info['freq_current']:.0f}M")
    return text


def _format_memory(info: dict, no_color: bool = False) -> Text:
    """Format memory info as compact text."""
    text = Text()
    text.append("RAM ")
    used = bytes_to_gb(info["used"])
    total = bytes_to_gb(info["total"])
    pct = info["percent"]

    if no_color:
        text.append(f"{used}/{total}G ({pct:.0f}%)")
    else:
        color = "green" if pct < 60 else "yellow" if pct < 80 else "red"
        text.append(f"{used}/{total}G", style="bold")
        text.append(f" ({pct:.0f}%)", style=color)
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


def _format_gpu(gpus: list | None, no_color: bool = False) -> Text | None:
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
        color = "green" if load < 60 else "yellow" if load < 80 else "red"
        text.append(f"{load:.0f}%", style=color)

    mem_used = gpu["memory_used"] / 1024
    mem_total = gpu["memory_total"] / 1024
    text.append(f" {mem_used:.1f}/{mem_total:.1f}G")

    if gpu["temperature"]:
        temp = gpu["temperature"]
        if no_color:
            text.append(f" {temp}°C")
        else:
            color = "green" if temp < 65 else "yellow" if temp < 80 else "red"
            text.append(f" {temp}°C", style=color)

    return text


def build_brief_line(no_color: bool = False, no_gpu: bool = False) -> Text:
    """Build a single line with all key metrics."""
    cpu_info = get_cpu_info()
    mem_info = get_memory_info()
    net_info = get_network_info()
    gpu_info = get_gpu_info() if not no_gpu else None

    line = Text()
    line.append_text(_format_cpu(cpu_info, no_color))
    line.append(" │ ", style="dim")
    line.append_text(_format_memory(mem_info, no_color))
    line.append(" │ ", style="dim")
    line.append_text(_format_network(net_info, no_color))

    if gpu_info:
        gpu_text = _format_gpu(gpu_info, no_color)
        if gpu_text:
            line.append(" │ ", style="dim")
            line.append_text(gpu_text)

    return line


def print_brief(console: Console, no_color: bool = False, no_gpu: bool = False) -> None:
    """Print a single line of key metrics."""
    get_network_info()
    time.sleep(1)
    console.print(build_brief_line(no_color, no_gpu))


def run_brief_watch(
    console: Console,
    refresh_rate: float = 1.0,
    no_color: bool = False,
    no_gpu: bool = False,
) -> None:
    """Run brief display in watch mode."""
    get_network_info()
    time.sleep(0.5)

    with Live(
        build_brief_line(no_color, no_gpu),
        console=console,
        refresh_per_second=1 / refresh_rate,
        transient=False,
    ) as live:
        try:
            while True:
                time.sleep(refresh_rate)
                live.update(build_brief_line(no_color, no_gpu))
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
                proc.wait(timeout=3)
    except Exception:
        pass
    finally:
        _PID_FILE.unlink(missing_ok=True)


def run_title_mode(
    console: Console,
    refresh_rate: float = 2.0,
    no_gpu: bool = False,
) -> None:
    """Run in terminal title mode - non-blocking background worker."""
    _stop_existing_title_process()

    cmd = [
        sys.executable,
        "-m",
        "sysmon.display.title_worker",
        "--refresh",
        str(refresh_rate),
    ]
    if no_gpu:
        cmd.append("--no-gpu")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            start_new_session=True,
        )
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
        console.print(f"[red]Error starting title mode: {e}[/red]")


def stop_title_mode(console: Console) -> None:
    """Stop the background title process."""
    if not _PID_FILE.exists():
        console.print("[dim]Title mode is not running.[/dim]")
        return

    try:
        pid = int(_PID_FILE.read_text(encoding="utf-8").strip())
        if psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            if _is_title_worker_process(proc):
                proc.terminate()
                console.print(f"[green]✓[/green] Title mode stopped (PID: {pid})")
            else:
                console.print("[dim]PID file did not match a title worker.[/dim]")
        else:
            console.print("[dim]Title mode process was not running.[/dim]")
    except Exception as e:
        console.print(f"[red]Error stopping title mode: {e}[/red]")
    finally:
        _PID_FILE.unlink(missing_ok=True)
