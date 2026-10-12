"""Interactive live top processes view."""

from __future__ import annotations

import sys
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from sysmon.collectors.registry import collect_processes
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


class _TopState:
    """Mutable view state for the interactive top loop."""

    def __init__(self, sort_by: str, name_filter: str | None) -> None:
        self.sort_by = sort_by
        self.name_filter = name_filter
        self.filter_mode = False
        self.filter_buffer = name_filter or ""


def _apply_top_key(state: _TopState, key: str | None) -> bool:
    """Apply one key. Return False when the view should quit."""
    if state.filter_mode:
        if key == "\x1b":
            state.filter_mode = False
            state.filter_buffer = ""
            state.name_filter = None
            return True
        if key == "\r":
            state.filter_mode = False
            state.name_filter = state.filter_buffer or None
            return True
        if key in ("\x08", "\x7f"):
            state.filter_buffer = state.filter_buffer[:-1]
            return True
        if key is not None and len(key) == 1 and key.isprintable():
            state.filter_buffer += key
        return True

    if key == "q":
        return False
    if key == "c":
        state.sort_by = "cpu"
    elif key == "m":
        state.sort_by = "memory"
    elif key == "/":
        state.filter_mode = True
        state.filter_buffer = ""
    elif key == "\x1b":
        state.name_filter = None
    return True


def run_top_live(
    limit: int = 10,
    sort_by: str = "cpu",
    refresh_rate: float = 1.0,
    name_filter: str | None = None,
    warn: float = 80.0,
    critical: float = 95.0,
    mem_warn: float | None = None,
    mem_critical: float | None = None,
) -> None:
    """Run interactive top with runtime sort and filter."""
    console = Console()
    state = _TopState(sort_by, name_filter)

    def render() -> Group:
        processes = collect_processes(
            limit=limit,
            sort_by=state.sort_by,
            name_filter=state.name_filter,
        )
        main = process_panel(
            processes,
            sort_by=state.sort_by,
            name_filter=state.name_filter,
            warn=warn,
            critical=critical,
            mem_warn=mem_warn,
            mem_critical=mem_critical,
        )
        footer = Panel(
            _footer_text(state.filter_mode, state.filter_buffer),
            border_style="dim",
        )
        return Group(main, footer)

    with Live(render(), console=console, refresh_per_second=4, screen=True) as live:
        try:
            while True:
                if not _apply_top_key(state, _read_key()):
                    break
                try:
                    live.update(render())
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    live.update(Text(f"top error: {exc}", style="red"))
                time.sleep(refresh_rate)
        except KeyboardInterrupt:
            pass
