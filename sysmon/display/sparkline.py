"""Sparkline rendering for dashboard history."""

from collections import deque


class HistoryBuffer:
    """Fixed-length history buffer for sparklines."""

    def __init__(self, maxlen: int = 60) -> None:
        self._data: deque[float] = deque(maxlen=maxlen)

    def add(self, value: float) -> None:
        self._data.append(value)

    def values(self) -> list[float]:
        return list(self._data)


def render_sparkline(values: list[float], width: int = 30) -> str:
    """Render a sparkline string from numeric values."""
    if not values:
        return " " * width

    blocks = "▁▂▃▄▅▆▇█"
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values
        if len(sampled) < width:
            sampled = [0.0] * (width - len(sampled)) + sampled

    min_v = min(sampled)
    max_v = max(sampled)
    span = max_v - min_v

    chars = []
    for v in sampled:
        if span == 0:
            chars.append(blocks[0])
        else:
            idx = int((v - min_v) / span * (len(blocks) - 1))
            chars.append(blocks[idx])
    return "".join(chars)
