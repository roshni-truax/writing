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


def is_number(s):
    try:
        number(s)
    except ValueError:
        return False
    return True


def rows(body, most=1):
    """`label value` lines as (label, values) pairs. Blank lines and `//`
    comments are skipped.

    A row may carry up to `most` numbers, taken from the end of the line: as
    many as every row can spare, and as many as leave the labels distinct. So
    `part 1  41200` keeps its label and reads as one number, while
    `part one  41200 40000` reads as two. Quoting settles it outright, and is
    the way to say which a line like `"part 1" 41200 40000` is.
    """
    rows_ = []
    for line in body.split("\n"):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        quoted = re.match(r'^"([^"]*)"\s*(.*)$', line)
        if quoted:
            head, tail = [quoted.group(1)], quoted.group(2).split()
        else:
            head, tail = line.split(), []
            while head and is_number(head[-1]):
                tail.insert(0, head.pop())
        if not tail or not all(is_number(t) for t in tail):
            raise ValueError(f"cannot read a number from {line!r}")
        if len(tail) > most:
            raise ValueError(f"too many numbers on {line!r}: at most {most}, and a "
                             f"label ending in a number needs quoting")
        rows_.append((head, tail, bool(quoted), line))
    if not rows_:
        return []

    settled = {len(t) for _, t, q, _ in rows_ if q}
    if len(settled) > 1:
        raise ValueError("the quoted rows disagree on how many numbers they carry")

    def build(count):
        out = []
        for head, tail, q, line in rows_:
            if len(tail) < count:
                raise ValueError(f"every row needs {count} numbers; {line!r} has "
                                 f"{len(tail)}")
            keep = len(tail) - count  # the rest were part of the label all along
            label = head[0] if q else " ".join(head + tail[:keep])
            out.append((label.strip(), [number(t) for t in tail[keep:]]))
        return out

    if settled:
        return build(settled.pop())
    count = min(len(t) for _, t, _, _ in rows_)
    while count > 1:
        out = build(count)
        labels = [l for l, _ in out]
        if len(set(labels)) == len(labels):
            return out
        count -= 1  # the labels repeat, so a number of each was part of one
    return build(count)


def _ends(values, top, length):
    """Where each bar ends, in cells, shortest first.

    Bars sharing a row are drawn one over another with the shortest in
    front, so each colour owns the stretch where its bar is the shortest one
    covering it. A cell carries one colour, so the boundaries inside land on
    whole cells; only the outermost tip keeps its eighth, which is the tip a
    reader measures the length by.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    out, prev = [], 0
    for n, i in enumerate(order):
        cells = max(0.0, min(1.0, values[i] / top if top else 0)) * length
        if n == len(order) - 1:
            full = max(prev, min(length, int(cells)))
            rest = max(0, min(8, int(round((cells - full) * 8))))
            partial = EIGHTHS_H[rest] if full < length and rest else None
            out.append((i, prev, full, partial))
            prev = full + (1 if partial else 0)
        else:
            end = max(prev, min(length, round(cells)))
            out.append((i, prev, end, None))
            prev = end
    return out


def nested_h(values, top, width, tones):
    """One row of nested horizontal bars as (text, tone) segments, padded to
    `width`. `tones` gives a tone per value, in the order they were written."""
    segs = []
    for i, start, end, partial in _ends(values, top, width):
        text = "█" * (end - start) + (partial or "")
        if text:
            segs.append((text, tones[i]))
    drawn = sum(len(t) for t, _ in segs)
    if drawn < width:
        segs.append((" " * (width - drawn), "fg"))
    return segs


def nested_v(values, top, height, tones):
    """One column of nested vertical bars as (character, tone) per row, top
    row first."""
    col = [(" ", "fg")] * height
    for i, start, end, partial in _ends(values, top, height):
        for k in range(start, end):
            col[height - 1 - k] = ("█", tones[i])
        if partial:
            col[height - 1 - end] = (EIGHTHS_V[EIGHTHS_H.index(partial)], tones[i])
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
