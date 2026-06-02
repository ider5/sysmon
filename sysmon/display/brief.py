"""Brief single-line display mode."""

import sys
import threading
import time

from rich.console import Console
from rich.live import Live
from rich.text import Text

from sysmon.collectors.cpu import get_cpu_info
from sysmon.collectors.memory import get_memory_info, bytes_to_gb
from sysmon.collectors.network import get_network_info, format_bytes, format_speed
from sysmon.collectors.gpu import get_gpu_info


def _format_cpu(info: dict, no_color: bool = False) -> Text:
    """Format CPU info as compact text."""
    text = Text()
    text.append("CPU ")
    pct = info['percent']
    if no_color:
        text.append(f"{pct:.0f}%")
    else:
        color = "green" if pct < 60 else "yellow" if pct < 80 else "red"
        text.append(f"{pct:.0f}%", style=color)

    if info['freq_current']:
        text.append(f" {info['freq_current']:.0f}M")
    return text


def _format_memory(info: dict, no_color: bool = False) -> Text:
    """Format memory info as compact text."""
    text = Text()
    text.append("RAM ")
    used = bytes_to_gb(info['used'])
    total = bytes_to_gb(info['total'])
    pct = info['percent']

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
        text.append(format_speed(info['speed_up']), style="green")
        text.append(" ↓", style="cyan")
        text.append(format_speed(info['speed_down']), style="cyan")
    return text


def _format_gpu(gpus: list | None, no_color: bool = False) -> Text | None:
    """Format GPU info as compact text."""
    if not gpus:
        return None

    gpu = gpus[0]  # Show first GPU only
    text = Text()
    text.append("GPU ")

    load = gpu['load']
    if no_color:
        text.append(f"{load:.0f}%")
    else:
        color = "green" if load < 60 else "yellow" if load < 80 else "red"
        text.append(f"{load:.0f}%", style=color)

    mem_used = gpu['memory_used'] / 1024
    mem_total = gpu['memory_total'] / 1024
    text.append(f" {mem_used:.1f}/{mem_total:.1f}G")

    if gpu['temperature']:
        temp = gpu['temperature']
        if no_color:
            text.append(f" {temp}°C")
        else:
            color = "green" if temp < 65 else "yellow" if temp < 80 else "red"
            text.append(f" {temp}°C", style=color)

    return text


def build_brief_line(no_color: bool = False, no_gpu: bool = False) -> Text:
    """Build a single line with all key metrics.

    Args:
        no_color: If True, disable colors
        no_gpu: If True, hide GPU info

    Returns:
        Rich Text object with formatted metrics
    """
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
    """Print a single line of key metrics.

    Args:
        console: Rich Console instance
        no_color: Disable colors
        no_gpu: Hide GPU info
    """
    # Get two samples for network speed
    get_network_info()
    time.sleep(1)

    console.print(build_brief_line(no_color, no_gpu))


def run_brief_watch(console: Console, refresh_rate: float = 1.0,
                    no_color: bool = False, no_gpu: bool = False) -> None:
    """Run brief display in watch mode (auto-refresh).

    Args:
        console: Rich Console instance
        refresh_rate: Seconds between refreshes
        no_color: Disable colors
        no_gpu: Hide GPU info
    """
    # Initial network sample
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


def _build_brief_string(no_gpu: bool = False) -> str:
    """Build a plain text brief string for terminal title.

    Args:
        no_gpu: Hide GPU info

    Returns:
        Plain text string without Rich formatting
    """
    cpu_info = get_cpu_info()
    mem_info = get_memory_info()
    net_info = get_network_info()
    gpu_info = get_gpu_info() if not no_gpu else None

    parts = [
        f"CPU {cpu_info['percent']:.0f}%",
        f"RAM {bytes_to_gb(mem_info['used'])}/{bytes_to_gb(mem_info['total'])}G ({mem_info['percent']:.0f}%)",
        f"↑{format_speed(net_info['speed_up'])} ↓{format_speed(net_info['speed_down'])}",
    ]

    if gpu_info:
        gpu = gpu_info[0]
        gpu_str = f"GPU {gpu['load']:.0f}%"
        gpu_str += f" {gpu['memory_used']/1024:.1f}/{gpu['memory_total']/1024:.1f}G"
        if gpu['temperature']:
            gpu_str += f" {gpu['temperature']}°C"
        parts.append(gpu_str)

    return " │ ".join(parts)


import subprocess
from pathlib import Path

# PID file location
_PID_FILE = Path.home() / '.sysmon_title.pid'


def _title_worker_script(refresh_rate: float = 2.0, no_gpu: bool = False) -> str:
    """Generate Python script for background title worker."""
    return f'''
import sys
import time
import ctypes
import traceback

from sysmon.collectors.cpu import get_cpu_info
from sysmon.collectors.memory import get_memory_info, bytes_to_gb
from sysmon.collectors.network import get_network_info, format_speed
from sysmon.collectors.gpu import get_gpu_info

def set_title(title):
    """Set terminal title using platform-specific method."""
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    else:
        sys.stdout.write(f"\\033]0;{{title}}\\007")
        sys.stdout.flush()

# Initial network sample
get_network_info()
time.sleep(0.5)

while True:
    try:
        cpu = get_cpu_info()
        mem = get_memory_info()
        net = get_network_info()
        gpus = get_gpu_info() if {not no_gpu} else None

        parts = [
            f"CPU {{cpu['percent']:.0f}}%",
            f"RAM {{bytes_to_gb(mem['used'])}}/{{bytes_to_gb(mem['total'])}}G ({{mem['percent']:.0f}}%)",
            f"↑{{format_speed(net['speed_up'])}} ↓{{format_speed(net['speed_down'])}}",
        ]

        if gpus:
            gpu = gpus[0]
            gpu_str = f"GPU {{gpu['load']:.0f}}% {{gpu['memory_used']/1024:.1f}}/{{gpu['memory_total']/1024:.1f}}G"
            if gpu['temperature']:
                gpu_str += f" {{gpu['temperature']}}°C"
            parts.append(gpu_str)

        title = " │ ".join(parts)
        set_title(title)
    except Exception as e:
        # Log error to file for debugging
        with open("C:/Users/50427/sysmon_title_error.log", "a") as f:
            f.write(f"{{time.strftime('%Y-%m-%d %H:%M:%S')}}: {{traceback.format_exc()}}\\n")
    time.sleep({refresh_rate})
'''


def _stop_existing_title_process():
    """Stop existing title process if running."""
    if _PID_FILE.exists():
        try:
            pid = int(_PID_FILE.read_text().strip())
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                # Check if it's our sysmon process
                if 'sysmon' in ' '.join(proc.cmdline()).lower():
                    proc.terminate()
                    time.sleep(0.5)
        except Exception:
            pass
        finally:
            _PID_FILE.unlink(missing_ok=True)


def run_title_mode(console: Console, refresh_rate: float = 2.0,
                   no_gpu: bool = False) -> None:
    """Run in terminal title mode - completely non-blocking.

    Starts a background process that updates terminal window title.
    Returns immediately, terminal is free to use.

    Args:
        console: Rich Console instance
        refresh_rate: Seconds between updates
        no_gpu: Hide GPU info
    """
    import psutil

    # Stop any existing title process
    _stop_existing_title_process()

    # Get Python executable
    python_exe = sys.executable

    # Build the worker script
    script = _title_worker_script(refresh_rate, no_gpu)

    # Start background process
    try:
        proc = subprocess.Popen(
            [python_exe, '-c', script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            start_new_session=True,
        )

        # Save PID
        _PID_FILE.write_text(str(proc.pid))

        console.print(f"[green]✓[/green] Title mode started (PID: {proc.pid})")
        console.print("[dim]System info will appear in terminal title bar.[/dim]")
        console.print(f"[dim]To stop: sysmon brief --stop[/dim]")

        # Check if running in VS Code
        if 'TERM_PROGRAM' in __import__('os').environ:
            if __import__('os').environ['TERM_PROGRAM'] == 'vscode':
                console.print()
                console.print("[yellow]⚠[/yellow] VS Code terminal may not show title updates.")
                console.print("[dim]For best results, use Windows Terminal or other standard terminal.[/dim]")
    except Exception as e:
        console.print(f"[red]Error starting title mode: {e}[/red]")


def stop_title_mode(console: Console) -> None:
    """Stop the background title process.

    Args:
        console: Rich Console instance
    """
    import psutil

    if not _PID_FILE.exists():
        console.print("[dim]Title mode is not running.[/dim]")
        return

    try:
        pid = int(_PID_FILE.read_text().strip())
        if psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            proc.terminate()
            console.print(f"[green]✓[/green] Title mode stopped (PID: {pid})")
        else:
            console.print("[dim]Title mode process was not running.[/dim]")
    except Exception as e:
        console.print(f"[red]Error stopping title mode: {e}[/red]")
    finally:
        _PID_FILE.unlink(missing_ok=True)
