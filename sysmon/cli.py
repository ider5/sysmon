"""SysMon CLI entry point."""

import typer
from rich.console import Console

from sysmon import __version__

app = typer.Typer(
    name="sysmon",
    help="A beautiful system monitoring CLI tool.",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"sysmon v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """SysMon - System monitoring made beautiful."""


@app.command()
def dashboard(
    refresh: float = typer.Option(
        1.0, "--refresh", "-r",
        help="Refresh interval in seconds.",
        min=0.1,
        max=10.0,
    ),
) -> None:
    """Launch the real-time monitoring dashboard."""
    from sysmon.display.dashboard import run_dashboard
    run_dashboard(refresh_rate=refresh)


@app.command()
def snapshot(
    section: str = typer.Argument(
        "all",
        help="Section to show: all, cpu, memory, network, gpu.",
    ),
) -> None:
    """Print a one-shot system snapshot."""
    from sysmon.display.snapshot import print_snapshot

    valid_sections = ["all", "cpu", "memory", "network", "gpu"]
    if section not in valid_sections:
        console.print(f"[red]Unknown section: {section}[/red]")
        console.print(f"Valid sections: {', '.join(valid_sections)}")
        raise typer.Exit(code=1)

    # Get two samples for network speed
    from sysmon.collectors.network import get_network_info
    import time
    get_network_info()
    time.sleep(1)

    print_snapshot(console, section=section)


@app.command()
def cpu() -> None:
    """Show CPU information."""
    from sysmon.collectors.cpu import get_cpu_info, get_per_core_usage
    from sysmon.display.snapshot import _print_cpu

    info = get_cpu_info()
    _print_cpu(console, info)

    cores = get_per_core_usage()
    console.print("\n[bold]Per-core usage:[/bold]")
    for i, pct in enumerate(cores):
        bar_len = 20
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        color = "red" if pct >= 90 else "yellow" if pct >= 70 else "green"
        console.print(f"  Core {i:2d}: [{bar}] [{color}]{pct:5.1f}%[/{color}]")


@app.command()
def memory() -> None:
    """Show Memory information."""
    from sysmon.collectors.memory import get_memory_info
    from sysmon.display.snapshot import _print_memory

    info = get_memory_info()
    _print_memory(console, info)


@app.command()
def network() -> None:
    """Show Network information."""
    from sysmon.collectors.network import get_network_info
    from sysmon.display.snapshot import _print_network
    import time

    # Two samples for speed
    get_network_info()
    time.sleep(1)

    info = get_network_info()
    _print_network(console, info)


@app.command()
def gpu() -> None:
    """Show GPU information."""
    from sysmon.collectors.gpu import get_gpu_info
    from sysmon.display.snapshot import _print_gpu

    info = get_gpu_info()
    _print_gpu(console, info)


if __name__ == "__main__":
    app()
