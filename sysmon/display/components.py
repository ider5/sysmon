"""Reusable UI components for sysmon display."""

from __future__ import annotations

import math
import platform
import time

import psutil
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
    try:
        boot_time = psutil.boot_time()
    except (OSError, RuntimeError, NotImplementedError):
        return "unknown"
    uptime_seconds = max(0.0, time.time() - boot_time)

    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def gradient_color(percent: float, warn: float = 80.0, critical: float = 95.0) -> str:
    """Get color based on percentage value and optional thresholds."""
    if percent >= critical:
        return "red"
    if percent >= warn:
        return "yellow"
    return "green"


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return float(value)


def progress_bar(
    percent: float,
    width: int = 30,
    warn: float = 80.0,
    critical: float = 95.0,
) -> Text:
    """Create a text-based progress bar with color coding."""
    number = _finite_number(percent)
    if number is None:
        text = Text()
        text.append("─" * width, style="grey50")
        text.append("   n/a", style="dim")
        return text
    percent = number
    filled = min(width, max(0, int(width * max(0.0, percent) / 100.0)))
    empty = width - filled
    color = gradient_color(percent, warn=warn, critical=critical)

    text = Text()
    text.append("━" * filled, style=color)
    text.append("─" * empty, style="grey50")
    text.append(f" {percent:5.1f}%", style=f"bold {color}")
    return text


def header_bar(hostname: str, os_name: str, uptime: str, notice: str | None = None) -> Panel:
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
    if notice:
        text.append("  │  ", style="dim")
        text.append(notice, style="bold red")

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


def one_line(value: object, fallback: str = "") -> str:
    """Collapse whitespace so an OS label cannot break a panel row."""
    text = " ".join(str("" if value is None else value).split())
    return text or fallback


def celsius(value: object) -> float | None:
    """Return a temperature in Celsius, keeping 0 and rejecting missing values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return float(value)


def gpu_panel(
    gpus: list | None,
    warn: float = 80.0,
    critical: float = 95.0,
) -> Panel:
    """Create GPU metrics panel.

    Args:
        gpus: List of GPU info dicts, or None if no GPU
        warn: Load/VRAM warn threshold percent
        critical: Load/VRAM critical threshold percent
    """
    if not isinstance(gpus, list) or not any(isinstance(item, dict) for item in gpus):
        text = Text("  ⚠ No GPU detected.", style="dim italic")
        return Panel(text, title="[bold yellow]🎮 GPU[/bold yellow]", border_style="yellow")

    text = Text()
    for gpu in gpus:
        if not isinstance(gpu, dict):
            continue
        gpu_id = gpu.get("id", "?")
        name = one_line(gpu.get("name"), "GPU")
        text.append(f"  🎮 GPU {gpu_id}: ", style="bold")
        text.append(f"{name}\n", style="bold white")

        load = _finite_number(gpu.get("load")) or 0.0
        text.append(f"  {'Utilization':<14}", style="bold")
        text.append_text(progress_bar(load, width=20, warn=warn, critical=critical))
        text.append("\n")

        memory_used = _finite_number(gpu.get("memory_used")) or 0.0
        memory_total = _finite_number(gpu.get("memory_total")) or 0.0
        mem_pct = (memory_used / memory_total * 100) if memory_total > 0 else 0
        text.append(f"  {'VRAM':<14}", style="bold")
        text.append_text(progress_bar(mem_pct, width=20, warn=warn, critical=critical))
        text.append(f"\n  {'':14}{memory_used:.0f} / {memory_total:.0f} MB\n", style="dim")

        # Temperature
        temp = celsius(gpu.get("temperature"))
        if temp is not None:
            temp_color = "red" if temp >= 80 else "yellow" if temp >= 65 else "green"
            text.append(f"  {'Temperature':<14}", style="bold")
            text.append(f"🌡  {temp:g}°C\n", style=temp_color)

        text.append("\n")

    return Panel(text, title="[bold yellow]🎮 GPU[/bold yellow]", border_style="yellow")
