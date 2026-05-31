"""Real-time terminal dashboard using Rich Live."""

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


def _progress_bar(percent: float, width: int = 30) -> str:
    """Create a text-based progress bar."""
    filled = int(width * percent / 100)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {percent:5.1f}%"


def _color_percent(percent: float) -> str:
    """Return color-coded percentage string."""
    if percent >= 90:
        return f"[bold red]{percent:.1f}%[/bold red]"
    elif percent >= 70:
        return f"[yellow]{percent:.1f}%[/yellow]"
    else:
        return f"[green]{percent:.1f}%[/green]"


def _build_cpu_panel() -> Panel:
    """Build CPU metrics panel."""
    info = get_cpu_info()
    cores = get_per_core_usage()

    text = Text()
    text.append(f"  Overall: ", style="bold")
    text.append(_color_percent(info["percent"]) + "\n")
    text.append(f"  {_progress_bar(info['percent'])}\n\n")
    text.append(f"  Cores: {info['count_physical']} physical / {info['count_logical']} logical\n")
    if info["freq_current"]:
        text.append(f"  Freq: {info['freq_current']:.0f} MHz")
        if info["freq_max"]:
            text.append(f" / {info['freq_max']:.0f} MHz max")
        text.append("\n")

    # Per-core mini bars
    if cores:
        text.append("\n  Per-core:\n")
        for i, pct in enumerate(cores):
            bar_len = 15
            filled = int(bar_len * pct / 100)
            bar = "█" * filled + "░" * (bar_len - filled)
            text.append(f"    {i:2d}: [{bar}] {pct:5.1f}%\n")

    return Panel(text, title="[bold cyan]CPU[/bold cyan]", border_style="cyan")


def _build_memory_panel() -> Panel:
    """Build Memory metrics panel."""
    info = get_memory_info()

    text = Text()
    text.append(f"  RAM Usage: ", style="bold")
    text.append(_color_percent(info["percent"]) + "\n")
    text.append(f"  {_progress_bar(info['percent'])}\n")
    text.append(f"  {bytes_to_gb(info['used'])} GB / {bytes_to_gb(info['total'])} GB\n")
    text.append(f"  Available: {bytes_to_gb(info['available'])} GB\n\n")

    if info["swap_total"] > 0:
        text.append(f"  Swap: ", style="bold")
        text.append(_color_percent(info["swap_percent"]) + "\n")
        text.append(f"  {_progress_bar(info['swap_percent'])}\n")
        text.append(f"  {bytes_to_gb(info['swap_used'])} GB / {bytes_to_gb(info['swap_total'])} GB\n")

    return Panel(text, title="[bold magenta]Memory[/bold magenta]", border_style="magenta")


def _build_network_panel() -> Panel:
    """Build Network metrics panel."""
    info = get_network_info()

    text = Text()
    text.append(f"  ↑ Upload:   ", style="bold")
    text.append(f"{format_speed(info['speed_up'])}\n", style="green")
    text.append(f"  ↓ Download: ", style="bold")
    text.append(f"{format_speed(info['speed_down'])}\n", style="cyan")
    text.append(f"\n")
    text.append(f"  Total Sent:     {format_bytes(info['bytes_sent'])}\n")
    text.append(f"  Total Received: {format_bytes(info['bytes_recv'])}\n")
    text.append(f"  Packets Sent:   {info['packets_sent']:,}\n")
    text.append(f"  Packets Recv:   {info['packets_recv']:,}\n")

    return Panel(text, title="[bold green]Network[/bold green]", border_style="green")


def _build_gpu_panel() -> Panel:
    """Build GPU metrics panel."""
    gpus = get_gpu_info()

    if gpus is None:
        text = Text("  No GPU detected or GPUtil not available.", style="dim")
        return Panel(text, title="[bold yellow]GPU[/bold yellow]", border_style="yellow")

    text = Text()
    for gpu in gpus:
        text.append(f"  GPU {gpu['id']}: ", style="bold")
        text.append(f"{gpu['name']}\n")
        text.append(f"  Utilization: ", style="bold")
        text.append(_color_percent(gpu["load"]) + "\n")
        text.append(f"  {_progress_bar(gpu['load'])}\n")
        mem_pct = (gpu["memory_used"] / gpu["memory_total"] * 100) if gpu["memory_total"] > 0 else 0
        text.append(f"  VRAM: {gpu['memory_used']:.0f} / {gpu['memory_total']:.0f} MB")
        text.append(f" ({mem_pct:.1f}%)\n")
        if gpu["temperature"]:
            temp = gpu["temperature"]
            style = "red" if temp >= 80 else "yellow" if temp >= 65 else "green"
            text.append(f"  Temperature: ")
            text.append(f"{temp}°C\n", style=style)
        text.append("\n")

    return Panel(text, title="[bold yellow]GPU[/bold yellow]", border_style="yellow")


def build_dashboard() -> Layout:
    """Build the full dashboard layout."""
    layout = Layout()
    layout.split_column(
        Layout(name="top", size=20),
        Layout(name="bottom"),
    )
    layout["top"].split_row(
        Layout(name="cpu"),
        Layout(name="memory"),
    )
    layout["bottom"].split_row(
        Layout(name="network"),
        Layout(name="gpu"),
    )

    layout["cpu"].update(_build_cpu_panel())
    layout["memory"].update(_build_memory_panel())
    layout["network"].update(_build_network_panel())
    layout["gpu"].update(_build_gpu_panel())

    return layout


def run_dashboard(refresh_rate: float = 1.0) -> None:
    """Run the real-time dashboard.

    Args:
        refresh_rate: Seconds between refreshes.
    """
    console = Console()
    with Live(
        build_dashboard(),
        console=console,
        refresh_per_second=1 / refresh_rate,
        screen=True,
    ) as live:
        try:
            while True:
                import time
                time.sleep(refresh_rate)
                live.update(build_dashboard())
        except KeyboardInterrupt:
            pass
