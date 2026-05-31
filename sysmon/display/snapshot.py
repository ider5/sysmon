"""Snapshot mode - one-shot system info output (neofetch style)."""

import platform

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sysmon.collectors.cpu import get_cpu_info
from sysmon.collectors.memory import get_memory_info, bytes_to_gb
from sysmon.collectors.network import get_network_info, format_bytes, format_speed
from sysmon.collectors.gpu import get_gpu_info
from sysmon.display.components import (
    ascii_logo,
    progress_bar,
    color_percent,
    metric_row,
    gpu_panel,
    _get_os_name,
    _get_uptime,
)


def print_snapshot(console: Console, section: str = "all") -> None:
    """Print system snapshot.

    Args:
        console: Rich Console instance.
        section: Which section to show: 'all', 'cpu', 'memory', 'network', 'gpu'
    """
    sections = {
        "all": _print_all,
        "cpu": _print_cpu,
        "memory": _print_memory,
        "network": _print_network,
        "gpu": _print_gpu,
    }

    handler = sections.get(section, _print_all)
    handler(console)


def _print_all(console: Console) -> None:
    """Print all system information with ASCII logo."""
    # Get all info
    hostname = platform.node()
    os_name = _get_os_name()
    arch = platform.machine()
    processor = platform.processor() or "Unknown"
    uptime = _get_uptime()
    cpu_info = get_cpu_info()
    mem_info = get_memory_info()
    net_info = get_network_info()
    gpu_info = get_gpu_info()

    # Print ASCII logo + system info side by side
    logo_text = ascii_logo()

    sys_text = Text()
    sys_text.append("  System Information\n", style="bold underline")
    sys_text.append("\n")
    sys_text.append(f"  {'Host':<12}", style="bold")
    sys_text.append(f"{hostname}\n", style="bold white")
    sys_text.append(f"  {'OS':<12}", style="bold")
    sys_text.append(f"{os_name}\n", style="bold blue")
    sys_text.append(f"  {'Arch':<12}", style="bold")
    sys_text.append(f"{arch}\n", style="bold white")
    sys_text.append(f"  {'CPU':<12}", style="bold")
    sys_text.append(f"{processor}\n", style="dim")
    sys_text.append(f"  {'Uptime':<12}", style="bold")
    sys_text.append(f"{uptime}\n", style="bold green")

    # Create a table to hold logo and system info
    info_table = Table(show_header=False, box=None, padding=0)
    info_table.add_column("logo", ratio=2)
    info_table.add_column("sys", ratio=3)
    info_table.add_row(logo_text, sys_text)

    console.print(Panel(info_table, style="on grey11", padding=(1, 2)))

    # Print metrics panels
    _print_cpu(console, cpu_info)
    _print_memory(console, mem_info)
    _print_network(console, net_info)
    console.print(gpu_panel(gpu_info))


def _print_cpu(console: Console, info: dict = None) -> None:
    """Print CPU information."""
    if info is None:
        info = get_cpu_info()

    text = Text()
    text.append(f"  {'Usage':<14}", style="bold")
    text.append_text(progress_bar(info["percent"], width=25))
    text.append("\n")

    text.append(f"  {'Cores':<14}", style="bold")
    text.append(f"{info['count_physical']} cores / {info['count_logical']} threads\n", style="bold white")

    if info["freq_current"]:
        text.append(f"  {'Frequency':<14}", style="bold")
        text.append(f"{info['freq_current']:.0f} MHz\n", style="bold white")

    console.print(Panel(text, title="[bold cyan]📊 CPU[/bold cyan]", border_style="cyan"))


def _print_memory(console: Console, info: dict = None) -> None:
    """Print Memory information."""
    if info is None:
        info = get_memory_info()

    text = Text()
    text.append(f"  {'RAM':<14}", style="bold")
    text.append_text(progress_bar(info["percent"], width=25))
    text.append(f"\n  {'':14}")
    text.append(f"{bytes_to_gb(info['used'])} / {bytes_to_gb(info['total'])} GB\n", style="bold white")

    if info["swap_total"] > 0:
        text.append(f"  {'Swap':<14}", style="bold")
        text.append_text(progress_bar(info["swap_percent"], width=25))
        text.append(f"\n  {'':14}")
        text.append(f"{bytes_to_gb(info['swap_used'])} / {bytes_to_gb(info['swap_total'])} GB\n", style="bold white")

    console.print(Panel(text, title="[bold magenta]💾 Memory[/bold magenta]", border_style="magenta"))


def _print_network(console: Console, info: dict = None) -> None:
    """Print Network information."""
    if info is None:
        info = get_network_info()

    text = Text()
    text.append(f"  {'↑ Upload':<14}", style="bold")
    text.append(format_speed(info["speed_up"]) + "\n", style="green")

    text.append(f"  {'↓ Download':<14}", style="bold")
    text.append(format_speed(info["speed_down"]) + "\n", style="cyan")

    text.append("  " + "─" * 30 + "\n", style="dim")

    text.append(f"  {'Sent':<14}", style="bold")
    text.append(format_bytes(info["bytes_sent"]) + "\n", style="dim")

    text.append(f"  {'Received':<14}", style="bold")
    text.append(format_bytes(info["bytes_recv"]) + "\n", style="dim")

    console.print(Panel(text, title="[bold green]🌐 Network[/bold green]", border_style="green"))


def _print_gpu(console: Console, info: list = None) -> None:
    """Print GPU information."""
    if info is None:
        info = get_gpu_info()

    console.print(gpu_panel(info))
