"""Snapshot mode - one-shot system info output (neofetch style)."""

import platform
import time

import psutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sysmon.collectors.cpu import get_cpu_info
from sysmon.collectors.memory import get_memory_info, bytes_to_gb
from sysmon.collectors.network import get_network_info, format_bytes, format_speed
from sysmon.collectors.gpu import get_gpu_info


def _get_system_info() -> dict:
    """Get basic system information."""
    uname = platform.uname()
    boot_time = psutil.boot_time()
    uptime_seconds = time.time() - boot_time

    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)

    uptime_str = f"{days}d {hours}h {minutes}m" if days > 0 else f"{hours}h {minutes}m"

    return {
        "os": f"{uname.system} {uname.release}",
        "hostname": uname.node,
        "arch": uname.machine,
        "processor": uname.processor or platform.processor(),
        "uptime": uptime_str,
    }


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
    """Print all system information."""
    sys_info = _get_system_info()
    cpu_info = get_cpu_info()
    mem_info = get_memory_info()
    net_info = get_network_info()
    gpu_info = get_gpu_info()

    # System info panel
    sys_text = Text()
    sys_text.append(f"  OS:        ", style="bold")
    sys_text.append(f"{sys_info['os']}\n")
    sys_text.append(f"  Hostname:  ", style="bold")
    sys_text.append(f"{sys_info['hostname']}\n")
    sys_text.append(f"  Arch:      ", style="bold")
    sys_text.append(f"{sys_info['arch']}\n")
    sys_text.append(f"  CPU:       ", style="bold")
    sys_text.append(f"{sys_info['processor']}\n")
    sys_text.append(f"  Uptime:    ", style="bold")
    sys_text.append(f"{sys_info['uptime']}\n")

    console.print(Panel(sys_text, title="[bold]System[/bold]", border_style="blue"))

    # CPU panel
    _print_cpu(console, cpu_info)

    # Memory panel
    _print_memory(console, mem_info)

    # Network panel
    _print_network(console, net_info)

    # GPU panel
    _print_gpu(console, gpu_info)


def _print_cpu(console: Console, info: dict = None) -> None:
    """Print CPU information."""
    if info is None:
        info = get_cpu_info()

    text = Text()
    text.append(f"  Usage:     ", style="bold")
    text.append(f"{info['percent']:.1f}%\n")
    text.append(f"  Cores:     ", style="bold")
    text.append(f"{info['count_physical']} physical / {info['count_logical']} logical\n")
    if info["freq_current"]:
        text.append(f"  Frequency: ", style="bold")
        text.append(f"{info['freq_current']:.0f} MHz\n")

    console.print(Panel(text, title="[bold cyan]CPU[/bold cyan]", border_style="cyan"))


def _print_memory(console: Console, info: dict = None) -> None:
    """Print Memory information."""
    if info is None:
        info = get_memory_info()

    text = Text()
    text.append(f"  RAM:   ", style="bold")
    text.append(f"{bytes_to_gb(info['used'])} / {bytes_to_gb(info['total'])} GB")
    text.append(f" ({info['percent']:.1f}%)\n")

    if info["swap_total"] > 0:
        text.append(f"  Swap:  ", style="bold")
        text.append(f"{bytes_to_gb(info['swap_used'])} / {bytes_to_gb(info['swap_total'])} GB")
        text.append(f" ({info['swap_percent']:.1f}%)\n")

    console.print(Panel(text, title="[bold magenta]Memory[/bold magenta]", border_style="magenta"))


def _print_network(console: Console, info: dict = None) -> None:
    """Print Network information."""
    if info is None:
        info = get_network_info()

    text = Text()
    text.append(f"  Upload:    ", style="bold")
    text.append(f"{format_speed(info['speed_up'])}\n", style="green")
    text.append(f"  Download:  ", style="bold")
    text.append(f"{format_speed(info['speed_down'])}\n", style="cyan")
    text.append(f"  Sent:      ", style="bold")
    text.append(f"{format_bytes(info['bytes_sent'])}\n")
    text.append(f"  Received:  ", style="bold")
    text.append(f"{format_bytes(info['bytes_recv'])}\n")

    console.print(Panel(text, title="[bold green]Network[/bold green]", border_style="green"))


def _print_gpu(console: Console, info: list = None) -> None:
    """Print GPU information."""
    if info is None:
        info = get_gpu_info()

    if info is None:
        text = Text("  No GPU detected.", style="dim")
        console.print(Panel(text, title="[bold yellow]GPU[/bold yellow]", border_style="yellow"))
        return

    for gpu in info:
        text = Text()
        text.append(f"  Name:  ", style="bold")
        text.append(f"{gpu['name']}\n")
        text.append(f"  Load:  ", style="bold")
        text.append(f"{gpu['load']:.1f}%\n")
        text.append(f"  VRAM:  ", style="bold")
        text.append(f"{gpu['memory_used']:.0f} / {gpu['memory_total']:.0f} MB\n")
        if gpu["temperature"]:
            text.append(f"  Temp:  ", style="bold")
            text.append(f"{gpu['temperature']}°C\n")

        console.print(Panel(text, title=f"[bold yellow]GPU {gpu['id']}[/bold yellow]", border_style="yellow"))
