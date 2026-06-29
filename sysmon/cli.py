"""SysMon CLI entry point."""

import time
from typing import Literal, Optional

import typer
from rich.console import Console

from sysmon import __version__
from sysmon.config import load_config, write_default_config
from sysmon.paths import get_config_path

app = typer.Typer(
    name="sysmon",
    help="A beautiful system monitoring CLI tool.",
    add_completion=False,
)
config_app = typer.Typer(help="Manage sysmon configuration.")
app.add_typer(config_app, name="config")
console = Console()

VALID_SECTIONS = ["all", "cpu", "memory", "network", "disk", "gpu", "process"]
OutputFormat = Literal["rich", "json"]


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"sysmon v{__version__}")
        raise typer.Exit()


def _validate_format(output_format: str) -> OutputFormat:
    if output_format not in ("rich", "json"):
        console.print(f"[red]Unknown format: {output_format}[/red]")
        console.print("Valid formats: rich, json")
        raise typer.Exit(code=1)
    return output_format  # type: ignore[return-value]


def _resolve_format(cli_format: Optional[str]) -> str:
    settings = load_config()
    return cli_format if cli_format is not None else settings.default_format


def _resolve_gpu_enabled(cli_no_gpu: bool) -> bool:
    settings = load_config()
    return settings.enable_gpu and settings.modules.gpu and not cli_no_gpu


def _emit_json(data: dict) -> None:
    from sysmon.export import to_json

    print(to_json(data))


def _wait_for_rate_sampling(sample_interval: float) -> None:
    from sysmon.collectors.disk import get_disk_info
    from sysmon.collectors.network import get_network_info

    settings = load_config()
    get_network_info(settings.network_interfaces)
    get_disk_info(settings.disk_mounts)
    time.sleep(sample_interval)


@config_app.command("init")
def config_init(
    force: bool = typer.Option(
        False, "--force",
        help="Overwrite an existing config file.",
    ),
) -> None:
    """Create a default config file at ~/.config/sysmon/config.toml."""
    path = get_config_path()
    if path.exists() and not force:
        console.print(f"[yellow]Config already exists:[/yellow] {path}")
        console.print("[dim]Use --force to overwrite.[/dim]")
        raise typer.Exit(code=1)

    write_default_config()
    console.print(f"[green]✓[/green] Config written to {path}")


@config_app.command("path")
def config_path() -> None:
    """Print the config file path."""
    print(get_config_path())


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit.",
    ),
    print_completion: Optional[str] = typer.Option(
        None, "--print-completion",
        help="Print shell completion script (bash, zsh, tcsh).",
    ),
) -> None:
    """SysMon - System monitoring made beautiful."""
    if print_completion:
        try:
            import shtab
            import typer.main

            print(shtab.complete(typer.main.get_command(app), shell=print_completion))
        except ImportError:
            console.print("[red]shtab is required for shell completion.[/red]")
            console.print("[dim]Install with: pip install shtab[/dim]")
            raise typer.Exit(code=1) from None
        raise typer.Exit()


@app.command()
def dashboard(
    refresh: Optional[float] = typer.Option(
        None, "--refresh", "-r",
        help="Refresh interval in seconds.",
        min=0.1,
        max=10.0,
    ),
    no_gpu: bool = typer.Option(
        False, "--no-gpu",
        help="Hide GPU information.",
    ),
) -> None:
    """Launch the real-time monitoring dashboard."""
    from sysmon.display.dashboard import run_dashboard

    settings = load_config()
    refresh_rate = refresh if refresh is not None else settings.refresh_interval
    run_dashboard(
        refresh_rate=refresh_rate,
        include_gpu=_resolve_gpu_enabled(no_gpu),
    )


@app.command()
def snapshot(
    section: str = typer.Argument(
        "all",
        help="Section to show: all, cpu, memory, network, disk, gpu, process.",
    ),
    sample_interval: Optional[float] = typer.Option(
        None, "--sample-interval", "-s",
        help="Seconds to wait for network/disk speed sampling.",
        min=0.1,
        max=10.0,
    ),
    output_format: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="Output format: rich or json.",
    ),
    no_gpu: bool = typer.Option(
        False, "--no-gpu",
        help="Hide GPU information.",
    ),
) -> None:
    """Print a one-shot system snapshot."""
    settings = load_config()
    fmt = _validate_format(_resolve_format(output_format))
    interval = (
        sample_interval if sample_interval is not None else settings.sample_interval
    )
    include_gpu = _resolve_gpu_enabled(no_gpu)

    if section not in VALID_SECTIONS:
        console.print(f"[red]Unknown section: {section}[/red]")
        console.print(f"Valid sections: {', '.join(VALID_SECTIONS)}")
        raise typer.Exit(code=1)

    _wait_for_rate_sampling(interval)

    if fmt == "json":
        from sysmon.export import collect_all, collect_section

        if section == "all":
            _emit_json(collect_all(include_gpu=include_gpu))
        else:
            _emit_json(collect_section(section, include_gpu=include_gpu))
        return

    from sysmon.display.snapshot import print_snapshot

    print_snapshot(console, section=section, include_gpu=include_gpu)


@app.command()
def top(
    limit: Optional[int] = typer.Option(
        None, "--limit", "-n",
        help="Number of processes to show.",
        min=1,
        max=50,
    ),
    sort_by: str = typer.Option(
        "cpu", "--sort",
        help="Sort by cpu or memory.",
    ),
    filter_name: Optional[str] = typer.Option(
        None, "--filter",
        help="Filter processes by name (case-insensitive substring).",
    ),
    watch: bool = typer.Option(
        False, "--watch", "-w",
        help="Interactive live view with runtime sort/filter keys.",
    ),
    refresh: Optional[float] = typer.Option(
        None, "--refresh", "-r",
        help="Refresh interval for watch mode.",
        min=0.2,
        max=10.0,
    ),
    output_format: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="Output format: rich or json.",
    ),
) -> None:
    """Show top processes by CPU or memory usage."""
    settings = load_config()
    fmt = _validate_format(_resolve_format(output_format))
    count = limit if limit is not None else settings.process_limit
    sort_key = sort_by if sort_by in ("cpu", "memory") else "cpu"
    refresh_rate = refresh if refresh is not None else settings.refresh_interval

    if watch:
        if fmt == "json":
            console.print("[red]JSON output is not supported with --watch.[/red]")
            raise typer.Exit(code=1)
        from sysmon.display.top_live import run_top_live

        run_top_live(
            limit=count,
            sort_by=sort_key,
            refresh_rate=refresh_rate,
            name_filter=filter_name,
        )
        return

    from sysmon.collectors.process import get_top_processes

    processes = get_top_processes(
        limit=count,
        sort_by=sort_key,
        name_filter=filter_name,
    )

    if fmt == "json":
        _emit_json({
            "processes": processes,
            "sort_by": sort_key,
            "filter": filter_name,
        })
        return

    from sysmon.display.panels import process_panel

    console.print(process_panel(processes, sort_by=sort_key, name_filter=filter_name))


@app.command()
def cpu(
    output_format: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="Output format: rich or json.",
    ),
) -> None:
    """Show CPU information."""
    fmt = _validate_format(_resolve_format(output_format))

    if fmt == "json":
        from sysmon.export import collect_section

        _emit_json(collect_section("cpu"))
        return

    from rich.text import Text

    from sysmon.collectors.cpu import get_cpu_snapshot
    from sysmon.display.components import progress_bar
    from sysmon.display.snapshot import _print_cpu

    snapshot_data = get_cpu_snapshot()
    _print_cpu(console, snapshot_data)

    cores = snapshot_data["cores"]
    console.print("\n[bold]Per-core usage:[/bold]")
    for i, pct in enumerate(cores):
        text = Text()
        text.append(f"  Core {i:2d} ", style="dim")
        text.append_text(progress_bar(pct, width=20))
        console.print(text)


@app.command()
def memory(
    output_format: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="Output format: rich or json.",
    ),
) -> None:
    """Show Memory information."""
    fmt = _validate_format(_resolve_format(output_format))

    if fmt == "json":
        from sysmon.export import collect_section

        _emit_json(collect_section("memory"))
        return

    from sysmon.collectors.memory import get_memory_info
    from sysmon.display.snapshot import _print_memory

    _print_memory(console, get_memory_info())


@app.command()
def network(
    sample_interval: Optional[float] = typer.Option(
        None, "--sample-interval", "-s",
        help="Seconds to wait for network speed sampling.",
        min=0.1,
        max=10.0,
    ),
    output_format: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="Output format: rich or json.",
    ),
) -> None:
    """Show Network information."""
    settings = load_config()
    fmt = _validate_format(_resolve_format(output_format))
    interval = (
        sample_interval if sample_interval is not None else settings.sample_interval
    )

    from sysmon.collectors.network import get_network_info

    get_network_info(settings.network_interfaces)
    time.sleep(interval)

    if fmt == "json":
        from sysmon.export import collect_section

        _emit_json(collect_section("network"))
        return

    from sysmon.display.snapshot import _print_network

    _print_network(console, get_network_info(settings.network_interfaces))


@app.command()
def disk(
    sample_interval: Optional[float] = typer.Option(
        None, "--sample-interval", "-s",
        help="Seconds to wait for disk I/O speed sampling.",
        min=0.1,
        max=10.0,
    ),
    output_format: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="Output format: rich or json.",
    ),
) -> None:
    """Show Disk usage and I/O information."""
    settings = load_config()
    fmt = _validate_format(_resolve_format(output_format))
    interval = (
        sample_interval if sample_interval is not None else settings.sample_interval
    )

    from sysmon.collectors.disk import get_disk_info

    get_disk_info(settings.disk_mounts)
    time.sleep(interval)

    if fmt == "json":
        from sysmon.export import collect_section

        _emit_json(collect_section("disk"))
        return

    from sysmon.display.snapshot import _print_disk

    _print_disk(console, get_disk_info(settings.disk_mounts))


@app.command()
def gpu(
    output_format: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="Output format: rich or json.",
    ),
) -> None:
    """Show GPU information."""
    fmt = _validate_format(_resolve_format(output_format))

    if fmt == "json":
        from sysmon.export import collect_section

        _emit_json(collect_section("gpu"))
        return

    from sysmon.collectors.gpu import get_gpu_info
    from sysmon.display.snapshot import _print_gpu

    _print_gpu(console, get_gpu_info())


@app.command()
def brief(
    watch: bool = typer.Option(
        False, "--watch", "-w",
        help="Watch mode: auto-refresh display.",
    ),
    title: bool = typer.Option(
        False, "--title", "-t",
        help="Title mode: update terminal window title (non-intrusive).",
    ),
    stop: bool = typer.Option(
        False, "--stop",
        help="Stop title mode background process.",
    ),
    refresh: Optional[float] = typer.Option(
        None, "--refresh", "-r",
        help="Refresh interval in seconds.",
        min=0.5,
        max=10.0,
    ),
    no_color: bool = typer.Option(
        False, "--no-color",
        help="Disable colors (for copy-paste).",
    ),
    no_gpu: bool = typer.Option(
        False, "--no-gpu",
        help="Hide GPU information.",
    ),
    output_format: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="Output format: rich or json.",
    ),
) -> None:
    """Show brief one-line system status."""
    from sysmon.display.brief import (
        print_brief,
        run_brief_watch,
        run_title_mode,
        stop_title_mode,
    )

    if stop:
        stop_title_mode(console)
        return

    settings = load_config()
    fmt = _validate_format(_resolve_format(output_format))
    refresh_rate = (
        refresh if refresh is not None else settings.brief_refresh_interval
    )
    include_gpu = _resolve_gpu_enabled(no_gpu)

    if fmt == "json":
        if title or watch:
            console.print(
                "[red]JSON output is not supported with --title or --watch.[/red]"
            )
            raise typer.Exit(code=1)

        from sysmon.collectors.network import get_network_info
        from sysmon.export import collect_brief

        get_network_info(settings.network_interfaces)
        time.sleep(settings.sample_interval)
        _emit_json(collect_brief(include_gpu=include_gpu))
        return

    if title:
        run_title_mode(console, refresh_rate=refresh_rate, no_gpu=not include_gpu)
    elif watch:
        run_brief_watch(
            console,
            refresh_rate=refresh_rate,
            no_color=no_color,
            no_gpu=not include_gpu,
        )
    else:
        print_brief(console, no_color=no_color, no_gpu=not include_gpu)


if __name__ == "__main__":
    app()
