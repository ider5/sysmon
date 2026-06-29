"""Reusable UI components for sysmon display."""

import platform
import time

import psutil
from rich.bar import Bar
from rich.panel import Panel
from rich.text import Text

from sysmon import __version__


def _get_os_name() -> str:
    """Get accurate OS name, correctly identifying Windows 11."""
    import sys
    uname = platform.uname()

    if uname.system == "Windows":
        try:
            build = sys.getwindowsversion().build
            if build >= 22000:
                return "Windows 11"
            else:
                return "Windows 10"
        except Exception:
            return f"Windows {uname.release}"
    else:
        return f"{uname.system} {uname.release}"


def _get_uptime() -> str:
    """Get system uptime as a formatted string."""
    boot_time = psutil.boot_time()
    uptime_seconds = time.time() - boot_time

    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def gradient_color(percent: float) -> str:
    """Get color based on percentage value.

    Green -> Yellow -> Red gradient:
    - 0-60%: green
    - 60-80%: yellow
    - 80-100%: red
    """
    if percent >= 80:
        return "red"
    elif percent >= 60:
        return "yellow"
    else:
        return "green"


def gradient_bar(percent: float, width: int = 30) -> Bar:
    """Create a Rich Bar with gradient color based on percentage.

    Args:
        percent: Value from 0-100
        width: Bar width in characters
    """
    color = gradient_color(percent)
    return Bar(
        size=100,
        begin=0,
        end=percent,
        width=width,
        color=color,
        bgcolor="grey23",
    )


def progress_bar(percent: float, width: int = 30) -> Text:
    """Create a text-based progress bar with color coding.

    Args:
        percent: Value from 0-100
        width: Bar width in characters
    """
    filled = int(width * percent / 100)
    empty = width - filled
    color = gradient_color(percent)

    text = Text()
    text.append("━" * filled, style=color)
    text.append("─" * empty, style="grey50")
    text.append(f" {percent:5.1f}%", style=f"bold {color}")
    return text


def color_percent(percent: float) -> Text:
    """Return color-coded percentage text.

    Args:
        percent: Value from 0-100
    """
    color = gradient_color(percent)
    text = Text()
    text.append(f"{percent:.1f}%", style=f"bold {color}")
    return text


def metric_row(label: str, value: str, style: str = "") -> Text:
    """Create a standard metric row with label and value.

    Args:
        label: Metric name
        value: Metric value
        style: Optional Rich style for value
    """
    text = Text()
    text.append(f"  {label:<14}", style="bold")
    text.append(value, style=style)
    return text


def header_bar(hostname: str, os_name: str, uptime: str) -> Panel:
    """Create the dashboard header bar with system info.

    Args:
        hostname: Computer hostname
        os_name: Operating system name
        uptime: System uptime string
    """
    text = Text()
    text.append("⚡ ", style="bold yellow")
    text.append("sysmon", style="bold cyan")
    text.append(f" v{__version__}", style="dim")
    text.append("  │  ", style="dim")
    text.append(f"💻 {hostname}", style="bold")
    text.append("  │  ", style="dim")
    text.append(f"{os_name}", style="bold blue")
    text.append("  │  ", style="dim")
    text.append(f"⏱  {uptime}", style="bold green")

    return Panel(
        text,
        style="on grey11",
        padding=(0, 1),
    )


def ascii_logo() -> Text:
    """Create ASCII art logo for sysmon."""
    logo = """
   _____             __  __  ___
  / ___/__  _______  / / /  |/  /__
  \\__ \\/ / / / __ \\/ / / /|_/ / _ \\
 ___/ / /_/ / / / / / / /  / /  __/
/____/\\__,_/_/ /_/_/ /_/  /_/\\___/
"""
    text = Text()
    text.append(logo, style="bold cyan")
    return text


def gpu_panel(gpus: list | None) -> Panel:
    """Create GPU metrics panel.

    Args:
        gpus: List of GPU info dicts, or None if no GPU
    """
    if gpus is None:
        text = Text("  ⚠ No GPU detected or GPUtil not available.", style="dim italic")
        return Panel(text, title="[bold yellow]🎮 GPU[/bold yellow]", border_style="yellow")

    text = Text()
    for gpu in gpus:
        # GPU name
        text.append(f"  🎮 GPU {gpu['id']}: ", style="bold")
        text.append(f"{gpu['name']}\n", style="bold white")

        # Utilization bar
        text.append(f"  {'Utilization':<14}", style="bold")
        text.append_text(progress_bar(gpu["load"], width=20))
        text.append("\n")

        # VRAM
        mem_pct = (gpu["memory_used"] / gpu["memory_total"] * 100) if gpu["memory_total"] > 0 else 0
        text.append(f"  {'VRAM':<14}", style="bold")
        text.append_text(progress_bar(mem_pct, width=20))
        text.append(f"\n  {'':14}{gpu['memory_used']:.0f} / {gpu['memory_total']:.0f} MB\n", style="dim")

        # Temperature
        if gpu["temperature"]:
            temp = gpu["temperature"]
            temp_color = "red" if temp >= 80 else "yellow" if temp >= 65 else "green"
            text.append(f"  {'Temperature':<14}", style="bold")
            text.append(f"🌡  {temp}°C\n", style=temp_color)

        text.append("\n")

    return Panel(text, title="[bold yellow]🎮 GPU[/bold yellow]", border_style="yellow")
