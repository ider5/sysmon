"""Shared metric panel builders for dashboard and snapshot."""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from sysmon.collectors.memory import bytes_to_gb
from sysmon.collectors.network import format_bytes, format_speed
from sysmon.display.components import progress_bar
from sysmon.display.sparkline import render_sparkline


def build_cpu_text(
    info: dict,
    cores: list[float] | None = None,
    *,
    compact: bool = False,
    warn: float = 80.0,
    critical: float = 95.0,
    history: list[float] | None = None,
) -> Text:
    """Build CPU metrics text."""
    text = Text()
    usage_label = "Overall" if compact else "Usage"
    text.append(f"  {usage_label:<14}", style="bold")
    text.append_text(progress_bar(info["percent"], width=25, warn=warn, critical=critical))
    text.append("\n")

    if history:
        text.append(f"  {'History':<14}", style="bold")
        text.append(render_sparkline(history, width=25) + "\n", style="cyan")

    text.append(f"  {'Cores':<14}", style="bold")
    text.append(
        f"{info['count_physical']} cores / {info['count_logical']} threads\n",
        style="bold white",
    )

    if info["freq_current"]:
        text.append(f"  {'Frequency':<14}", style="bold")
        text.append(f"{info['freq_current']:.0f} MHz\n", style="bold white")

    if cores and compact:
        text.append("\n  ", style="bold")
        text.append("Per-core Usage\n", style="bold underline")
        for i in range(0, len(cores), 2):
            text.append(f"  {i:2d} ", style="dim")
            text.append_text(progress_bar(cores[i], width=12, warn=warn, critical=critical))
            if i + 1 < len(cores):
                text.append(f"  {i+1:2d} ", style="dim")
                text.append_text(
                    progress_bar(cores[i + 1], width=12, warn=warn, critical=critical)
                )
            text.append("\n")

    return text


def cpu_panel(
    info: dict,
    cores: list[float] | None = None,
    *,
    compact: bool = False,
    warn: float = 80.0,
    critical: float = 95.0,
    history: list[float] | None = None,
) -> Panel:
    """Build CPU metrics panel."""
    return Panel(
        build_cpu_text(
            info, cores, compact=compact, warn=warn, critical=critical, history=history
        ),
        title="[bold cyan]📊 CPU[/bold cyan]",
        border_style="cyan",
    )


def build_memory_text(
    info: dict,
    *,
    show_available: bool = False,
    warn: float = 80.0,
    critical: float = 95.0,
) -> Text:
    """Build memory metrics text."""
    text = Text()
    text.append(f"  {'RAM':<14}", style="bold")
    text.append_text(progress_bar(info["percent"], width=25, warn=warn, critical=critical))
    text.append(f"\n  {'':14}")
    text.append(
        f"{bytes_to_gb(info['used'])} / {bytes_to_gb(info['total'])} GB",
        style="bold white",
    )
    if show_available:
        text.append(f"  (Available: {bytes_to_gb(info['available'])} GB)\n", style="dim")
    else:
        text.append("\n", style="bold white")

    if info["swap_total"] > 0:
        if show_available:
            text.append("\n")
        text.append(f"  {'Swap':<14}", style="bold")
        text.append_text(progress_bar(info["swap_percent"], width=25, warn=warn, critical=critical))
        text.append(f"\n  {'':14}")
        text.append(
            f"{bytes_to_gb(info['swap_used'])} / {bytes_to_gb(info['swap_total'])} GB\n",
            style="bold white",
        )

    return text


def memory_panel(
    info: dict,
    *,
    show_available: bool = False,
    warn: float = 80.0,
    critical: float = 95.0,
) -> Panel:
    """Build memory metrics panel."""
    return Panel(
        build_memory_text(info, show_available=show_available, warn=warn, critical=critical),
        title="[bold magenta]💾 Memory[/bold magenta]",
        border_style="magenta",
    )


def build_network_text(
    info: dict,
    *,
    show_packets: bool = False,
    download_history: list[float] | None = None,
) -> Text:
    """Build network metrics text."""
    text = Text()
    interfaces = info.get("interfaces")

    if interfaces:
        for idx, iface in enumerate(interfaces):
            if idx > 0:
                text.append("  " + "─" * 30 + "\n", style="dim")
            text.append(f"  {iface['name']:<14}", style="bold underline white")
            text.append("\n")
            text.append(f"  {'↑ Upload':<14}", style="bold")
            text.append(format_speed(iface["speed_up"]) + "\n", style="green")
            text.append(f"  {'↓ Download':<14}", style="bold")
            text.append(format_speed(iface["speed_down"]) + "\n", style="cyan")
        text.append("  " + "─" * 30 + "\n", style="dim")
        text.append(f"  {'Total ↑':<14}", style="bold")
        text.append(format_speed(info["speed_up"]) + "\n", style="green")
        text.append(f"  {'Total ↓':<14}", style="bold")
        text.append(format_speed(info["speed_down"]) + "\n", style="cyan")
    else:
        text.append(f"  {'↑ Upload':<14}", style="bold")
        text.append(format_speed(info["speed_up"]) + "\n", style="green")

        text.append(f"  {'↓ Download':<14}", style="bold")
        text.append(format_speed(info["speed_down"]) + "\n", style="cyan")

    if download_history:
        text.append(f"  {'History':<14}", style="bold")
        text.append(render_sparkline(download_history, width=25) + "\n", style="cyan")

    text.append("  " + "─" * 30 + "\n", style="dim")

    text.append(f"  {'Sent':<14}", style="bold")
    text.append(format_bytes(info["bytes_sent"]) + "\n", style="dim")

    text.append(f"  {'Received':<14}", style="bold")
    text.append(format_bytes(info["bytes_recv"]) + "\n", style="dim")

    if show_packets:
        text.append(f"  {'Packets':<14}", style="bold")
        text.append(
            f"↑{info['packets_sent']:,} ↓{info['packets_recv']:,}\n",
            style="dim",
        )

    return text


def network_panel(
    info: dict,
    *,
    show_packets: bool = False,
    download_history: list[float] | None = None,
) -> Panel:
    """Build network metrics panel."""
    return Panel(
        build_network_text(
            info, show_packets=show_packets, download_history=download_history
        ),
        title="[bold green]🌐 Network[/bold green]",
        border_style="green",
    )


def build_disk_text(
    info: dict,
    *,
    warn: float = 80.0,
    critical: float = 95.0,
) -> Text:
    """Build disk metrics text."""
    text = Text()
    mounts = info.get("mounts") or [
        {
            "mount": info.get("mount", "?"),
            "percent": info.get("percent", 0),
            "used": info.get("used", 0),
            "total": info.get("total", 0),
        }
    ]

    for idx, mount_info in enumerate(mounts):
        if idx > 0:
            text.append("  " + "─" * 30 + "\n", style="dim")
        text.append(f"  {'Mount':<14}", style="bold")
        text.append(f"{mount_info['mount']}\n", style="bold white")
        text.append(f"  {'Usage':<14}", style="bold")
        text.append_text(
            progress_bar(mount_info["percent"], width=25, warn=warn, critical=critical)
        )
        text.append(f"\n  {'':14}")
        text.append(
            f"{format_bytes(mount_info['used'])} / {format_bytes(mount_info['total'])}\n",
            style="bold white",
        )

    text.append("  " + "─" * 30 + "\n", style="dim")
    text.append(f"  {'Read':<14}", style="bold")
    text.append(format_speed(info["read_speed"]) + "\n", style="cyan")
    text.append(f"  {'Write':<14}", style="bold")
    text.append(format_speed(info["write_speed"]) + "\n", style="magenta")
    return text


def disk_panel(
    info: dict,
    *,
    warn: float = 80.0,
    critical: float = 95.0,
) -> Panel:
    """Build disk metrics panel."""
    return Panel(
        build_disk_text(info, warn=warn, critical=critical),
        title="[bold blue]💿 Disk[/bold blue]",
        border_style="blue",
    )


def process_panel(
    processes: list[dict],
    *,
    sort_by: str = "cpu",
    name_filter: str | None = None,
) -> Panel:
    """Build top processes panel."""
    text = Text()
    title_suffix = f" (sort: {sort_by}"
    if name_filter:
        title_suffix += f", filter: {name_filter}"
    title_suffix += ")"

    if not processes:
        text.append("  No process data available.\n", style="dim")
    else:
        text.append(f"  {'PID':<8}{'Name':<22}{'CPU%':>8}{'MEM%':>8}{'RSS':>10}\n", style="bold")
        text.append("  " + "─" * 54 + "\n", style="dim")
        for proc in processes:
            text.append(f"  {proc['pid']:<8}", style="dim")
            name = proc["name"][:20]
            text.append(f"{name:<22}", style="white")
            text.append(f"{proc['cpu_percent']:>8.1f}", style="cyan")
            text.append(f"{proc['memory_percent']:>8.1f}", style="magenta")
            text.append(f"{proc['memory_mb']:>9.0f}M\n", style="dim")

    return Panel(
        text,
        title=f"[bold white]⚙ Processes{title_suffix}[/bold white]",
        border_style="white",
    )
