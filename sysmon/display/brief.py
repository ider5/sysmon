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


def run_title_mode(console: Console, refresh_rate: float = 2.0,
                   no_gpu: bool = False) -> None:
    """Run in terminal title mode - updates window title without affecting terminal.

    This mode runs in the background and updates the terminal window title.
    It does NOT interfere with normal terminal usage.

    Args:
        console: Rich Console instance
        refresh_rate: Seconds between updates
        no_gpu: Hide GPU info
    """
    # Initial network sample
    get_network_info()
    time.sleep(0.5)

    def _title_updater():
        """Background thread to update terminal title."""
        while True:
            try:
                title = _build_brief_string(no_gpu)
                # ANSI escape sequence to set terminal title
                sys.stdout.write(f'\033]0;{title}\007')
                sys.stdout.flush()
            except Exception:
                pass
            time.sleep(refresh_rate)

    # Start background thread
    t = threading.Thread(target=_title_updater, daemon=True)
    t.start()

    console.print("[dim]Terminal title mode started. System info will appear in window title.[/dim]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[dim]Title mode stopped.[/dim]")
