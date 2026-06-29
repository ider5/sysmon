"""Real-time terminal dashboard using Rich Live."""

from __future__ import annotations

import platform
import time

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from sysmon.collectors.cpu import get_cpu_snapshot
from sysmon.collectors.disk import get_disk_info
from sysmon.collectors.gpu import get_gpu_info
from sysmon.collectors.memory import get_memory_info
from sysmon.collectors.network import get_network_info
from sysmon.collectors.process import get_top_processes
from sysmon.config import SysmonConfig, load_config
from sysmon.display.components import _get_os_name, _get_uptime, gpu_panel, header_bar
from sysmon.display.panels import (
    cpu_panel,
    disk_panel,
    memory_panel,
    network_panel,
    process_panel,
)
from sysmon.display.sparkline import HistoryBuffer


def build_dashboard(
    include_gpu: bool = True,
    config: SysmonConfig | None = None,
    cpu_history: HistoryBuffer | None = None,
    net_history: HistoryBuffer | None = None,
) -> Layout:
    """Build the full dashboard layout."""
    settings = config or load_config()
    modules = settings.modules
    thresholds = settings.thresholds

    os_name = _get_os_name()
    hostname = platform.node()
    uptime = _get_uptime()

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="content"),
    )
    layout["header"].update(header_bar(hostname, os_name, uptime))

    active_panels: list[tuple[str, Panel]] = []

    if modules.cpu:
        cpu_snapshot = get_cpu_snapshot()
        if cpu_history is not None:
            cpu_history.add(cpu_snapshot["percent"])
        active_panels.append(
            (
                "cpu",
                cpu_panel(
                    cpu_snapshot,
                    cores=cpu_snapshot["cores"],
                    compact=True,
                    warn=thresholds.cpu_warn,
                    critical=thresholds.cpu_critical,
                    history=cpu_history.values() if cpu_history else None,
                ),
            )
        )

    if modules.memory:
        active_panels.append(
            (
                "memory",
                memory_panel(
                    get_memory_info(),
                    show_available=True,
                    warn=thresholds.memory_warn,
                    critical=thresholds.memory_critical,
                ),
            )
        )

    if modules.network:
        net_info = get_network_info()
        if net_history is not None:
            net_history.add(net_info["speed_down"])
        active_panels.append(
            (
                "network",
                network_panel(
                    net_info,
                    show_packets=True,
                    download_history=net_history.values() if net_history else None,
                ),
            )
        )

    if modules.disk:
        active_panels.append(
            (
                "disk",
                disk_panel(
                    get_disk_info(),
                    warn=thresholds.disk_warn,
                    critical=thresholds.disk_critical,
                ),
            )
        )

    if modules.gpu and include_gpu:
        active_panels.append(("gpu", gpu_panel(get_gpu_info())))

    if modules.process:
        active_panels.append(
            ("process", process_panel(get_top_processes(limit=settings.process_limit)))
        )

    if not active_panels:
        layout["content"].update(
            Panel(Text("  All modules disabled in config.", style="dim"))
        )
        return layout

    # Build grid rows (2 columns max per row)
    rows: list[list[tuple[str, Panel]]] = []
    row: list[tuple[str, Panel]] = []
    for item in active_panels:
        row.append(item)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    layout["content"].split_column(
        *[Layout(name=f"row{i}", ratio=1) for i in range(len(rows))]
    )
    for i, row_panels in enumerate(rows):
        if len(row_panels) == 1:
            layout["content"][f"row{i}"].update(row_panels[0][1])
        else:
            layout["content"][f"row{i}"].split_row(
                Layout(name=row_panels[0][0], ratio=1),
                Layout(name=row_panels[1][0], ratio=1),
            )
            layout["content"][f"row{i}"][row_panels[0][0]].update(row_panels[0][1])
            layout["content"][f"row{i}"][row_panels[1][0]].update(row_panels[1][1])

    return layout


def run_dashboard(refresh_rate: float = 1.0, include_gpu: bool = True) -> None:
    """Run the real-time dashboard."""
    console = Console()
    config = load_config()
    cpu_history = HistoryBuffer(maxlen=60)
    net_history = HistoryBuffer(maxlen=60)

    get_network_info()
    get_disk_info()
    time.sleep(0.5)

    with Live(
        build_dashboard(
            include_gpu=include_gpu,
            config=config,
            cpu_history=cpu_history,
            net_history=net_history,
        ),
        console=console,
        refresh_per_second=1 / refresh_rate,
        screen=True,
    ) as live:
        try:
            while True:
                time.sleep(refresh_rate)
                live.update(
                    build_dashboard(
                        include_gpu=include_gpu,
                        config=config,
                        cpu_history=cpu_history,
                        net_history=net_history,
                    )
                )
        except KeyboardInterrupt:
            pass
