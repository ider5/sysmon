"""Sparkline rendering for dashboard history."""

import math
from collections import deque


class HistoryBuffer:
    """Fixed-length history buffer for sparklines."""

    def __init__(self, maxlen: int = 60) -> None:
        self._data: deque[float] = deque(maxlen=max(1, maxlen))

    def add(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return
        if not math.isfinite(value):
            return
        self._data.append(float(value))

    def values(self) -> list[float]:
        return list(self._data)


def render_sparkline(values: list[float], width: int = 30) -> str:
    """Render a sparkline string from numeric values."""
    if width <= 0:
        return ""
    finite = [
        float(value)
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    ]
    if not finite:
        return " " * width

    blocks = "▁▂▃▄▅▆▇█"
    if len(finite) > width:
        step = len(finite) / width
        sampled = [finite[int(i * step)] for i in range(width)]
        sampled[-1] = finite[-1]
    else:
        sampled = finite
        if len(sampled) < width:
            pad = sampled[0]
            sampled = [pad] * (width - len(sampled)) + sampled

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
