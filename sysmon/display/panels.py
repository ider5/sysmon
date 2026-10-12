"""Shared metric panel builders for dashboard and snapshot."""

from __future__ import annotations

import math

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sysmon.collectors.memory import bytes_to_gb
from sysmon.collectors.network import format_bytes, format_speed
from sysmon.display.components import gradient_color, progress_bar
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
    text.append_text(progress_bar(_as_number(info.get("percent")), width=25, warn=warn, critical=critical))
    text.append("\n")

    if history:
        text.append(f"  {'History':<14}", style="bold")
        text.append(render_sparkline(history, width=25) + "\n", style="cyan")

    physical = int(_as_number(info.get("count_physical")))
    logical = int(_as_number(info.get("count_logical")))
    text.append(f"  {'Cores':<14}", style="bold")
    text.append(f"{physical} cores / {logical} threads\n", style="bold white")

    freq = _as_number(info.get("freq_current"))
    if freq:
        text.append(f"  {'Frequency':<14}", style="bold")
        text.append(f"{freq:.0f} MHz\n", style="bold white")

    if cores:
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
    history: list[float] | None = None,
) -> Text:
    """Build memory metrics text."""
    text = Text()
    text.append(f"  {'RAM':<14}", style="bold")
    text.append_text(progress_bar(_as_number(info.get("percent")), width=25, warn=warn, critical=critical))
    text.append("\n")
    if history:
        text.append(f"  {'History':<14}", style="bold")
        text.append(render_sparkline(history, width=25) + "\n", style="magenta")
    text.append(f"  {'':14}")
    text.append(
        f"{bytes_to_gb(_as_number(info.get('used')))} / {bytes_to_gb(_as_number(info.get('total')))} GB",
        style="bold white",
    )
    if show_available:
        text.append(
            f"  (Available: {bytes_to_gb(_as_number(info.get('available')))} GB)\n",
            style="dim",
        )
    else:
        text.append("\n", style="bold white")

    swap_total = _as_number(info.get("swap_total"))
    if swap_total > 0:
        if show_available:
            text.append("\n")
        text.append(f"  {'Swap':<14}", style="bold")
        text.append_text(
            progress_bar(_as_number(info.get("swap_percent")), width=25, warn=warn, critical=critical)
        )
        text.append(f"\n  {'':14}")
        text.append(
            f"{bytes_to_gb(_as_number(info.get('swap_used')))} / {bytes_to_gb(swap_total)} GB\n",
            style="bold white",
        )

    return text


def memory_panel(
    info: dict,
    *,
    show_available: bool = False,
    warn: float = 80.0,
    critical: float = 95.0,
    history: list[float] | None = None,
) -> Panel:
    """Build memory metrics panel."""
    return Panel(
        build_memory_text(
            info,
            show_available=show_available,
            warn=warn,
            critical=critical,
            history=history,
        ),
        title="[bold magenta]💾 Memory[/bold magenta]",
        border_style="magenta",
    )


def build_network_text(
    info: dict,
    *,
    show_packets: bool = False,
    download_history: list[float] | None = None,
    upload_history: list[float] | None = None,
) -> Text:
    """Build network metrics text."""
    text = Text()
    interfaces = info.get("interfaces")

    if isinstance(interfaces, list) and interfaces:
        for idx, iface in enumerate(interfaces):
            if not isinstance(iface, dict):
                continue
            if idx > 0:
                text.append("  " + "─" * 30 + "\n", style="dim")
            name = str(iface.get("name") or "unknown")
            text.append(f"  {name:<14}", style="bold underline white")
            text.append("\n")
            text.append(f"  {'↑ Upload':<14}", style="bold")
            text.append(format_speed(_as_number(iface.get("speed_up"))) + "\n", style="green")
            text.append(f"  {'↓ Download':<14}", style="bold")
            text.append(format_speed(_as_number(iface.get("speed_down"))) + "\n", style="cyan")
        text.append("  " + "─" * 30 + "\n", style="dim")
        text.append(f"  {'Total ↑':<14}", style="bold")
        text.append(format_speed(_as_number(info.get("speed_up"))) + "\n", style="green")
        if upload_history:
            text.append(f"  {'':14}")
            text.append(render_sparkline(upload_history, width=25) + "\n", style="green")
        text.append(f"  {'Total ↓':<14}", style="bold")
        text.append(format_speed(_as_number(info.get("speed_down"))) + "\n", style="cyan")
    else:
        text.append(f"  {'↑ Upload':<14}", style="bold")
        text.append(format_speed(_as_number(info.get("speed_up"))) + "\n", style="green")
        if upload_history:
            text.append(f"  {'':14}")
            text.append(render_sparkline(upload_history, width=25) + "\n", style="green")

        text.append(f"  {'↓ Download':<14}", style="bold")
        text.append(format_speed(_as_number(info.get("speed_down"))) + "\n", style="cyan")

    if download_history:
        text.append(f"  {'History':<14}", style="bold")
        text.append(render_sparkline(download_history, width=25) + "\n", style="cyan")

    text.append("  " + "─" * 30 + "\n", style="dim")

    text.append(f"  {'Sent':<14}", style="bold")
    text.append(format_bytes(_as_number(info.get("bytes_sent"))) + "\n", style="dim")

    text.append(f"  {'Received':<14}", style="bold")
    text.append(format_bytes(_as_number(info.get("bytes_recv"))) + "\n", style="dim")

    if show_packets:
        text.append(f"  {'Packets':<14}", style="bold")
        text.append(
            f"↑{int(_as_number(info.get('packets_sent'))):,} "
            f"↓{int(_as_number(info.get('packets_recv'))):,}\n",
            style="dim",
        )

    return text


def network_panel(
    info: dict,
    *,
    show_packets: bool = False,
    download_history: list[float] | None = None,
    upload_history: list[float] | None = None,
) -> Panel:
    """Build network metrics panel."""
    return Panel(
        build_network_text(
            info,
            show_packets=show_packets,
            download_history=download_history,
            upload_history=upload_history,
        ),
        title="[bold green]🌐 Network[/bold green]",
        border_style="green",
    )


def build_disk_text(
    info: dict,
    *,
    warn: float = 80.0,
    critical: float = 95.0,
    read_history: list[float] | None = None,
    write_history: list[float] | None = None,
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
        used = mount_info.get("used", 0)
        total = mount_info.get("total", 0)
        text.append(f"\n  {'':14}")
        text.append(
            f"{format_bytes(used if isinstance(used, (int, float)) else 0)} / "
            f"{format_bytes(total if isinstance(total, (int, float)) else 0)}\n",
            style="bold white",
        )
        free = mount_info.get("free")
        if isinstance(free, (int, float)) and not isinstance(free, bool):
            text.append(f"  {'Free':<14}", style="bold")
            text.append(format_bytes(free) + "\n", style="dim")

    text.append("  " + "─" * 30 + "\n", style="dim")
    text.append(f"  {'Read':<14}", style="bold")
    text.append(format_speed(info["read_speed"]) + "\n", style="cyan")
    if read_history:
        text.append(f"  {'':14}")
        text.append(render_sparkline(read_history, width=25) + "\n", style="cyan")
    text.append(f"  {'Write':<14}", style="bold")
    text.append(format_speed(info["write_speed"]) + "\n", style="magenta")
    if write_history:
        text.append(f"  {'':14}")
        text.append(render_sparkline(write_history, width=25) + "\n", style="magenta")
    return text


def disk_panel(
    info: dict,
    *,
    warn: float = 80.0,
    critical: float = 95.0,
    read_history: list[float] | None = None,
    write_history: list[float] | None = None,
) -> Panel:
    """Build disk metrics panel."""
    return Panel(
        build_disk_text(
            info,
            warn=warn,
            critical=critical,
            read_history=read_history,
            write_history=write_history,
        ),
        title="[bold blue]💿 Disk[/bold blue]",
        border_style="blue",
    )


def _as_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    number = float(value)
    if not math.isfinite(number):
        return 0.0
    return number


def process_panel(
    processes: list[dict],
    *,
    sort_by: str = "cpu",
    name_filter: str | None = None,
    warn: float = 80.0,
    critical: float = 95.0,
    mem_warn: float | None = None,
    mem_critical: float | None = None,
) -> Panel:
    """Build a bordered top-processes table."""
    memory_warn = warn if mem_warn is None else mem_warn
    memory_critical = critical if mem_critical is None else mem_critical
    title_suffix = f" (sort: {sort_by}"
    if name_filter:
        title_suffix += f", filter: {name_filter}"
    title_suffix += ")"

    table = Table(
        box=box.HEAVY,
        expand=True,
        show_header=True,
        show_lines=False,
        header_style="bold bright_cyan",
        border_style="bright_cyan",
        row_styles=["none", "on grey11"],
        pad_edge=True,
        padding=(0, 1),
    )
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column("PID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Name", overflow="ellipsis", no_wrap=True, min_width=12)
    table.add_column("CPU%", justify="left", no_wrap=True)
    table.add_column("MEM%", justify="right", no_wrap=True)
    table.add_column("RSS", justify="right", style="dim", no_wrap=True)

    if not processes:
        table.add_row("—", "—", "No matching processes", "—", "—", "—")
    else:
        for index, proc in enumerate(processes, start=1):
            cpu = _as_number(proc.get("cpu_percent"))
            mem = _as_number(proc.get("memory_percent"))
            rss = _as_number(proc.get("memory_mb"))
            mem_color = gradient_color(mem, warn=memory_warn, critical=memory_critical)
            table.add_row(
                str(index),
                str(proc.get("pid", "")),
                str(proc.get("name") or "unknown"),
                progress_bar(cpu, width=10, warn=warn, critical=critical),
                Text(f"{mem:.1f}%", style=f"bold {mem_color}"),
                f"{rss:.0f}M",
            )

    return Panel(
        table,
        title=f"[bold cyan]⚙ Processes{title_suffix}[/bold cyan]",
        border_style="bright_cyan",
        padding=(0, 1),
    )


def _format_remaining(seconds: int) -> str:
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _temperature_style(current: float, entry: dict) -> str:
    critical = entry.get("critical")
    high = entry.get("high")
    if isinstance(critical, (int, float)) and current >= critical:
        return "bold red"
    if isinstance(high, (int, float)) and current >= high:
        return "bold yellow"
    return "bold white"


def build_sensors_text(info: dict) -> Text:
    """Build battery and temperature text."""
    text = Text()
    battery = info.get("battery") if isinstance(info.get("battery"), dict) else None
    temperatures = info.get("temperatures") if isinstance(info.get("temperatures"), dict) else {}

    if battery is None and not temperatures:
        text.append("  No battery or temperature sensors\n", style="dim")
        return text

    if battery is not None:
        percent = float(battery.get("percent") or 0.0)
        text.append(f"  {'Battery':<14}", style="bold")
        text.append_text(progress_bar(percent, width=25))
        plugged = "plugged in" if battery.get("power_plugged") else "on battery"
        text.append(f"\n  {'Power':<14}", style="bold")
        text.append(plugged + "\n", style="bold white")
        secsleft = battery.get("secsleft")
        if isinstance(secsleft, (int, float)) and secsleft >= 0:
            text.append(f"  {'Remaining':<14}", style="bold")
            text.append(_format_remaining(int(secsleft)) + "\n", style="bold white")

    readings: list[tuple[str, dict]] = []
    for group, entries in temperatures.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                label = str(entry.get("label") or group or "temp")
                readings.append((label, entry))

    if readings:
        if battery is not None:
            text.append("  " + "─" * 30 + "\n", style="dim")
        shown = readings[:8]
        for label, entry in shown:
            current = entry.get("current")
            text.append(f"  {label[:14]:<14}", style="bold")
            if isinstance(current, (int, float)):
                text.append(f"{float(current):.1f}°C\n", style=_temperature_style(float(current), entry))
            else:
                text.append("n/a\n", style="dim")
        extra = len(readings) - len(shown)
        if extra > 0:
            text.append(f"  +{extra} more\n", style="dim")

    return text


def sensors_panel(info: dict) -> Panel:
    """Build battery and temperature panel."""
    return Panel(
        build_sensors_text(info),
        title="[bold bright_white]🌡 Sensors[/bold bright_white]",
        border_style="bright_white",
    )
