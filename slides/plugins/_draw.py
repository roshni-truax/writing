"""Shared pieces for the plugins that draw in characters. Not a plugin
itself: files starting with an underscore are skipped by the loader."""

import math
import re

EIGHTHS_H = " ▏▎▍▌▋▊▉█"  # a bar growing to the right, in eighths
EIGHTHS_V = " ▁▂▃▄▅▆▇█"  # a bar growing upward, in eighths


def number(s):
    """A number from text: 42, 4.2, 60%, 3/5, 1,200."""
    s = s.strip().replace(",", "")
    if s.endswith("%"):
        return float(s[:-1]) / 100
    if "/" in s:
        a, b = s.split("/", 1)
        return float(a) / float(b)
    return float(s)


def fmt(x):
    """A number as it would be written by hand: 42, 4.2, 0.35, 1200."""
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def rows(body):
    """`label value` lines as (label, value) pairs; the label may be missing
    or quoted. Blank lines and `//` comments are skipped."""
    out = []
    for line in body.split("\n"):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        m = re.match(r'^(?:"([^"]*)"|(.*?))\s*(\S+)$', line)
        label = m.group(1) if m.group(1) is not None else m.group(2)
        try:
            out.append((label.strip(), number(m.group(3))))
        except ValueError:
            raise ValueError(f"cannot read a number from {line!r}")
    return out


def hbar(fraction, width):
    """A horizontal bar `width` characters long, filled to `fraction`."""
    fraction = max(0.0, min(1.0, fraction))
    cells = fraction * width
    full = int(cells)
    rest = int(round((cells - full) * 8))
    bar = "█" * full + (EIGHTHS_H[rest] if full < width and rest else "")
    return bar.ljust(width)


def vbar(fraction, height):
    """The characters of a vertical bar, top row first."""
    fraction = max(0.0, min(1.0, fraction))
    cells = fraction * height
    full = int(cells)
    rest = int(round((cells - full) * 8))
    col = []
    for row in range(height):  # from the top
        from_bottom = height - row
        if from_bottom <= full:
            col.append("█")
        elif from_bottom == full + 1 and rest:
            col.append(EIGHTHS_V[rest])
        else:
            col.append(" ")
    return col


class Braille:
    """A dot canvas at 2x4 dots per character, the plotille idea. Coordinates
    are in dots, (0, 0) at the bottom left."""

    BITS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.cells = [[0] * width for _ in range(height)]

    def dot(self, x, y):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.width * 2 and 0 <= y < self.height * 4:
            row = self.height - 1 - y // 4
            self.cells[row][x // 2] |= self.BITS[3 - y % 4][x % 2]

    def line(self, x0, y0, x1, y1):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        n = int(math.ceil(steps))
        for k in range(n + 1):
            t = k / n
            self.dot(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)

    def render(self):
        return ["".join(chr(0x2800 + c) for c in row) for row in self.cells]


def scale(values, lo=None, hi=None):
    """(lo, hi) for a set of values, padded so a flat series still draws."""
    lo = min(values) if lo is None else lo
    hi = max(values) if hi is None else hi
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    return lo, hi
