"""Snapshot mode - one-shot system info output (neofetch style)."""

from __future__ import annotations

import platform

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sysmon.collectors.cpu import get_cpu_info
from sysmon.collectors.disk import get_disk_info
from sysmon.collectors.gpu import get_gpu_info
from sysmon.collectors.memory import get_memory_info
from sysmon.collectors.network import get_network_info
from sysmon.collectors.process import get_top_processes
from sysmon.config import load_config
from sysmon.display.components import _get_os_name, _get_uptime, ascii_logo, gpu_panel
from sysmon.display.panels import (
    cpu_panel,
    disk_panel,
    memory_panel,
    network_panel,
    process_panel,
)


def print_snapshot(
    console: Console,
    section: str = "all",
    include_gpu: bool = True,
) -> None:
    """Print system snapshot."""
    sections = {
        "all": lambda c: _print_all(c, include_gpu=include_gpu),
        "cpu": _print_cpu,
        "memory": _print_memory,
        "network": _print_network,
        "disk": _print_disk,
        "gpu": _print_gpu,
        "process": _print_process,
    }

    handler = sections.get(section, sections["all"])
    handler(console)


def _print_all(console: Console, include_gpu: bool = True) -> None:
    """Print all system information with ASCII logo."""
    settings = load_config()
    hostname = platform.node()
    os_name = _get_os_name()
    arch = platform.machine()
    processor = platform.processor() or "Unknown"
    uptime = _get_uptime()

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

    info_table = Table(show_header=False, box=None, padding=0)
    info_table.add_column("logo", ratio=2)
    info_table.add_column("sys", ratio=3)
    info_table.add_row(logo_text, sys_text)
    console.print(Panel(info_table, style="on grey11", padding=(1, 2)))

    if settings.modules.cpu:
        _print_cpu(console, get_cpu_info())
    if settings.modules.memory:
        _print_memory(console, get_memory_info())
    if settings.modules.network:
        _print_network(console, get_network_info(settings.network_interfaces))
    if settings.modules.disk:
        _print_disk(console, get_disk_info(settings.disk_mounts))
    if include_gpu and settings.modules.gpu:
        _print_gpu(console, get_gpu_info())
    if settings.modules.process:
        _print_process(console)


def _print_cpu(console: Console, info: dict | None = None) -> None:
    """Print CPU information."""
    settings = load_config()
    if info is None:
        info = get_cpu_info()
    console.print(
        cpu_panel(
            info,
            warn=settings.thresholds.cpu_warn,
            critical=settings.thresholds.cpu_critical,
        )
    )


def _print_memory(console: Console, info: dict | None = None) -> None:
    """Print Memory information."""
    settings = load_config()
    if info is None:
        info = get_memory_info()
    console.print(
        memory_panel(
            info,
            warn=settings.thresholds.memory_warn,
            critical=settings.thresholds.memory_critical,
        )
    )


def _print_network(console: Console, info: dict | None = None) -> None:
    """Print Network information."""
    settings = load_config()
    if info is None:
        info = get_network_info(settings.network_interfaces)
    console.print(network_panel(info))


def _print_disk(console: Console, info: dict | None = None) -> None:
    """Print Disk information."""
    settings = load_config()
    if info is None:
        info = get_disk_info(settings.disk_mounts)
    console.print(
        disk_panel(
            info,
            warn=settings.thresholds.disk_warn,
            critical=settings.thresholds.disk_critical,
        )
    )


def _print_gpu(console: Console, info: list | None = None) -> None:
    """Print GPU information."""
    if info is None:
        info = get_gpu_info()
    console.print(gpu_panel(info))


def _print_process(console: Console) -> None:
    """Print top processes."""
    settings = load_config()
    processes = get_top_processes(limit=settings.process_limit)
    console.print(process_panel(processes))
