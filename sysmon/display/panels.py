"""Shared metric panel builders for dashboard and snapshot."""

from rich.panel import Panel
from rich.text import Text

from sysmon.collectors.memory import bytes_to_gb
from sysmon.collectors.network import format_bytes, format_speed
from sysmon.display.components import progress_bar


def build_cpu_text(
    info: dict,
    cores: list[float] | None = None,
    *,
    compact: bool = False,
) -> Text:
    """Build CPU metrics text."""
    text = Text()
    usage_label = "Overall" if compact else "Usage"
    text.append(f"  {usage_label:<14}", style="bold")
    text.append_text(progress_bar(info["percent"], width=25))
    text.append("\n")

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
            text.append_text(progress_bar(cores[i], width=12))
            if i + 1 < len(cores):
                text.append(f"  {i+1:2d} ", style="dim")
                text.append_text(progress_bar(cores[i + 1], width=12))
            text.append("\n")

    return text


def cpu_panel(
    info: dict,
    cores: list[float] | None = None,
    *,
    compact: bool = False,
) -> Panel:
    """Build CPU metrics panel."""
    return Panel(
        build_cpu_text(info, cores, compact=compact),
        title="[bold cyan]📊 CPU[/bold cyan]",
        border_style="cyan",
    )


def build_memory_text(info: dict, *, show_available: bool = False) -> Text:
    """Build memory metrics text."""
    text = Text()
    text.append(f"  {'RAM':<14}", style="bold")
    text.append_text(progress_bar(info["percent"], width=25))
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
        text.append_text(progress_bar(info["swap_percent"], width=25))
        text.append(f"\n  {'':14}")
        text.append(
            f"{bytes_to_gb(info['swap_used'])} / {bytes_to_gb(info['swap_total'])} GB\n",
            style="bold white",
        )

    return text


def memory_panel(info: dict, *, show_available: bool = False) -> Panel:
    """Build memory metrics panel."""
    return Panel(
        build_memory_text(info, show_available=show_available),
        title="[bold magenta]💾 Memory[/bold magenta]",
        border_style="magenta",
    )


def build_network_text(info: dict, *, show_packets: bool = False) -> Text:
    """Build network metrics text."""
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

    if show_packets:
        text.append(f"  {'Packets':<14}", style="bold")
        text.append(
            f"↑{info['packets_sent']:,} ↓{info['packets_recv']:,}\n",
            style="dim",
        )

    return text


def network_panel(info: dict, *, show_packets: bool = False) -> Panel:
    """Build network metrics panel."""
    return Panel(
        build_network_text(info, show_packets=show_packets),
        title="[bold green]🌐 Network[/bold green]",
        border_style="green",
    )


def build_disk_text(info: dict) -> Text:
    """Build disk metrics text."""
    text = Text()
    text.append(f"  {'Mount':<14}", style="bold")
    text.append(f"{info['mount']}\n", style="bold white")

    text.append(f"  {'Usage':<14}", style="bold")
    text.append_text(progress_bar(info["percent"], width=25))
    text.append(f"\n  {'':14}")
    text.append(
        f"{format_bytes(info['used'])} / {format_bytes(info['total'])}\n",
        style="bold white",
    )

    text.append(f"  {'Read':<14}", style="bold")
    text.append(format_speed(info["read_speed"]) + "\n", style="cyan")

    text.append(f"  {'Write':<14}", style="bold")
    text.append(format_speed(info["write_speed"]) + "\n", style="magenta")

    return text


def disk_panel(info: dict) -> Panel:
    """Build disk metrics panel."""
    return Panel(
        build_disk_text(info),
        title="[bold blue]💿 Disk[/bold blue]",
        border_style="blue",
    )
