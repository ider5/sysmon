"""Real-time terminal dashboard using Rich Live."""

import platform
import time

from rich.console import Console
from rich.layout import Layout
from rich.live import Live

from sysmon.collectors.cpu import get_cpu_snapshot
from sysmon.collectors.disk import get_disk_info
from sysmon.collectors.gpu import get_gpu_info
from sysmon.collectors.memory import get_memory_info
from sysmon.collectors.network import get_network_info
from sysmon.display.components import _get_os_name, _get_uptime, gpu_panel, header_bar
from sysmon.display.panels import cpu_panel, disk_panel, memory_panel, network_panel


def build_dashboard(include_gpu: bool = True) -> Layout:
    """Build the full dashboard layout."""
    os_name = _get_os_name()
    hostname = platform.node()
    uptime = _get_uptime()

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="content"),
    )
    layout["header"].update(header_bar(hostname, os_name, uptime))

    layout["content"].split_column(
        Layout(name="top", ratio=1),
        Layout(name="bottom", ratio=1),
    )
    layout["content"]["top"].split_row(
        Layout(name="cpu", ratio=1),
        Layout(name="memory", ratio=1),
    )
    layout["content"]["bottom"].split_row(
        Layout(name="network", ratio=1),
        Layout(name="disk", ratio=1),
        Layout(name="gpu", ratio=1),
    )

    cpu_snapshot = get_cpu_snapshot()
    layout["content"]["cpu"].update(
        cpu_panel(cpu_snapshot, cores=cpu_snapshot["cores"], compact=True)
    )
    layout["content"]["memory"].update(
        memory_panel(get_memory_info(), show_available=True)
    )
    layout["content"]["network"].update(
        network_panel(get_network_info(), show_packets=True)
    )
    layout["content"]["disk"].update(disk_panel(get_disk_info()))
    layout["content"]["gpu"].update(
        gpu_panel(get_gpu_info() if include_gpu else None)
    )

    return layout


def run_dashboard(refresh_rate: float = 1.0, include_gpu: bool = True) -> None:
    """Run the real-time dashboard."""
    console = Console()

    get_network_info()
    get_disk_info()
    time.sleep(0.5)

    with Live(
        build_dashboard(include_gpu=include_gpu),
        console=console,
        refresh_per_second=1 / refresh_rate,
        screen=True,
    ) as live:
        try:
            while True:
                time.sleep(refresh_rate)
                live.update(build_dashboard(include_gpu=include_gpu))
        except KeyboardInterrupt:
            pass
