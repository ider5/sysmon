"""Interactive live top processes view."""

from __future__ import annotations

import sys
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from sysmon.collectors.process import get_top_processes
from sysmon.display.panels import process_panel


def _read_key() -> str | None:
    """Read a single key if available (non-blocking)."""
    if not sys.stdin.isatty():
        return None

    if sys.platform == "win32":
        import msvcrt

        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                msvcrt.getwch()
                return None
            return ch
        return None

    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return None


def _footer_text(filter_mode: bool, filter_buffer: str) -> Text:
    text = Text()
    text.append("c", style="cyan bold")
    text.append(" CPU  ", style="dim")
    text.append("m", style="magenta bold")
    text.append(" MEM  ", style="dim")
    text.append("/", style="yellow bold")
    text.append(" filter  ", style="dim")
    text.append("Esc", style="yellow bold")
    text.append(" clear  ", style="dim")
    text.append("q", style="red bold")
    text.append(" quit", style="dim")
    if filter_mode:
        text.append("  │  Filter: ", style="bold")
        text.append(filter_buffer, style="yellow")
        text.append("█", style="blink yellow")
    return text


def run_top_live(
    limit: int = 10,
    sort_by: str = "cpu",
    refresh_rate: float = 1.0,
    name_filter: str | None = None,
) -> None:
    """Run interactive top with runtime sort and filter."""
    console = Console()
    current_sort = sort_by
    current_filter = name_filter
    filter_mode = False
    filter_buffer = current_filter or ""

    def render() -> Group:
        processes = get_top_processes(
            limit=limit,
            sort_by=current_sort,
            name_filter=current_filter,
        )
        main = process_panel(
            processes,
            sort_by=current_sort,
            name_filter=current_filter,
        )
        footer = Panel(_footer_text(filter_mode, filter_buffer), border_style="dim")
        return Group(main, footer)

    with Live(render(), console=console, refresh_per_second=4, screen=True) as live:
        try:
            while True:
                key = _read_key()
                if key == "q":
                    break
                if key == "c":
                    current_sort = "cpu"
                elif key == "m":
                    current_sort = "memory"
                elif key == "/":
                    filter_mode = True
                    filter_buffer = ""
                elif key == "\x1b":
                    if filter_mode:
                        filter_mode = False
                        filter_buffer = ""
                    current_filter = None
                elif key == "\r" and filter_mode:
                    filter_mode = False
                    current_filter = filter_buffer or None
                elif filter_mode and key is not None:
                    if key in ("\x08", "\x7f"):
                        filter_buffer = filter_buffer[:-1]
                    elif len(key) == 1 and key.isprintable():
                        filter_buffer += key

                live.update(render())
                time.sleep(refresh_rate)
        except KeyboardInterrupt:
            pass
