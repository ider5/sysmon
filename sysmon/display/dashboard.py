"""Real-time terminal dashboard using Rich Live."""

import time

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sysmon.collectors.cpu import get_cpu_info, get_per_core_usage
from sysmon.collectors.memory import get_memory_info, bytes_to_gb
from sysmon.collectors.network import get_network_info, format_bytes, format_speed
from sysmon.collectors.gpu import get_gpu_info
from sysmon.display.components import (
    header_bar,
    progress_bar,
    color_percent,
    metric_row,
    gpu_panel,
    _get_os_name,
    _get_uptime,
)


def _build_cpu_panel() -> Panel:
    """Build CPU metrics panel."""
    info = get_cpu_info()
    cores = get_per_core_usage()

    text = Text()

    # Overall CPU usage
    text.append(f"  {'Overall':<14}", style="bold")
    text.append_text(progress_bar(info["percent"], width=25))
    text.append("\n")

    # Cores info
    text.append(f"  {'Cores':<14}", style="bold")
    text.append(f"{info['count_physical']} cores / {info['count_logical']} threads\n", style="bold white")

    # Frequency (only show if dynamic frequency detected)
    if info["freq_current"]:
        text.append(f"  {'Frequency':<14}", style="bold")
        text.append(f"{info['freq_current']:.0f} MHz\n", style="bold white")

    # Per-core mini bars (compact view)
    if cores:
        text.append("\n  ", style="bold")
        text.append("Per-core Usage\n", style="bold underline")

        # Show cores in 2 columns for better layout
        for i in range(0, len(cores), 2):
            # Left core
            text.append(f"  {i:2d} ", style="dim")
            text.append_text(progress_bar(cores[i], width=12))

            # Right core (if exists)
            if i + 1 < len(cores):
                text.append(f"  {i+1:2d} ", style="dim")
                text.append_text(progress_bar(cores[i + 1], width=12))
            text.append("\n")

    return Panel(text, title="[bold cyan]📊 CPU[/bold cyan]", border_style="cyan")


def _build_memory_panel() -> Panel:
    """Build Memory metrics panel."""
    info = get_memory_info()

    text = Text()

    # RAM
    text.append(f"  {'RAM':<14}", style="bold")
    text.append_text(progress_bar(info["percent"], width=25))
    text.append(f"\n  {'':14}")
    text.append(f"{bytes_to_gb(info['used'])} / {bytes_to_gb(info['total'])} GB", style="bold white")
    text.append(f"  (Available: {bytes_to_gb(info['available'])} GB)\n", style="dim")

    # Swap
    if info["swap_total"] > 0:
        text.append("\n")
        text.append(f"  {'Swap':<14}", style="bold")
        text.append_text(progress_bar(info["swap_percent"], width=25))
        text.append(f"\n  {'':14}")
        text.append(f"{bytes_to_gb(info['swap_used'])} / {bytes_to_gb(info['swap_total'])} GB\n", style="bold white")

    return Panel(text, title="[bold magenta]💾 Memory[/bold magenta]", border_style="magenta")


def _build_network_panel() -> Panel:
    """Build Network metrics panel."""
    info = get_network_info()

    text = Text()

    # Speed
    text.append(f"  {'↑ Upload':<14}", style="bold")
    text.append(format_speed(info["speed_up"]) + "\n", style="green")

    text.append(f"  {'↓ Download':<14}", style="bold")
    text.append(format_speed(info["speed_down"]) + "\n", style="cyan")

    # Separator
    text.append("  " + "─" * 30 + "\n", style="dim")

    # Totals
    text.append(f"  {'Sent':<14}", style="bold")
    text.append(format_bytes(info["bytes_sent"]) + "\n", style="dim")

    text.append(f"  {'Received':<14}", style="bold")
    text.append(format_bytes(info["bytes_recv"]) + "\n", style="dim")

    text.append(f"  {'Packets':<14}", style="bold")
    text.append(f"↑{info['packets_sent']:,} ↓{info['packets_recv']:,}\n", style="dim")

    return Panel(text, title="[bold green]🌐 Network[/bold green]", border_style="green")


def build_dashboard() -> Layout:
    """Build the full dashboard layout."""
    # Get system info for header
    os_name = _get_os_name()
    import platform
    hostname = platform.node()
    uptime = _get_uptime()

    layout = Layout()

    # Header + content
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="content"),
    )

    # Header bar
    layout["header"].update(header_bar(hostname, os_name, uptime))

    # Main content: 2x2 grid
    layout["content"].split_column(
        Layout(name="top", ratio=1),
        Layout(name="bottom", ratio=1),
    )
    layout["content"]["top"].split_row(
        Layout(name="cpu", ratio=1),
        Layout(name="memory", ratio=1),
    )
    layout["content"]["bottom"].split_row(
        Layout(name="network", ratio=1),
        Layout(name="gpu", ratio=1),
    )

    # Update panels
    layout["content"]["cpu"].update(_build_cpu_panel())
    layout["content"]["memory"].update(_build_memory_panel())
    layout["content"]["network"].update(_build_network_panel())
    layout["content"]["gpu"].update(gpu_panel(get_gpu_info()))

    return layout


def run_dashboard(refresh_rate: float = 1.0) -> None:
    """Run the real-time dashboard.

    Args:
        refresh_rate: Seconds between refreshes.
    """
    console = Console()

    # Initial network sample for speed calculation
    get_network_info()
    time.sleep(0.5)

    with Live(
        build_dashboard(),
        console=console,
        refresh_per_second=1 / refresh_rate,
        screen=True,
    ) as live:
        try:
            while True:
                time.sleep(refresh_rate)
                live.update(build_dashboard())
        except KeyboardInterrupt:
            pass
