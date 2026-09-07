"""chart: a chart drawn in characters. The first argument is the kind.

    ```chart hbar
    fiction     42
    philosophy  17
    letters      3
    ```

kinds
  hbar     `label value` rows, a bar to the right of each label (default
           when the rows have labels)
  bar      the same rows as upright columns with the labels beneath
  line     one series of numbers per line, comma or space separated, drawn
           in braille dots; up to three series, each a step dimmer
  scatter  `x y` rows as braille dots
  spark    one series as a single row of ▁▂▃▄▅▆▇█

options
  height=8       rows for bar, line and scatter
  width=60       columns, if not the whole grid
  max=100        the top of the scale (min= for the bottom)
  values=off     hide the figures on hbar and bar
  axis=off       drop the axis and its labels on line and scatter
  bar=3          the width of a column in `bar`
"""

import re

import _draw

TONES = ("fg", "dim", "faint")


def series(body):
    """Each non-empty line as a list of numbers."""
    out = []
    for line in body.split("\n"):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        out.append([_draw.number(t) for t in re.split(r"[,\s]+", line) if t])
    return out


def render(body, args, opts, width):
    width = int(opts.get("width", width))
    kind = args[0] if args else "hbar"
    if kind not in KINDS:
        raise ValueError(f"unknown chart kind {kind!r}; one of {', '.join(KINDS)}")
    lo = _draw.number(opts["min"]) if "min" in opts else None
    hi = _draw.number(opts["max"]) if "max" in opts else None
    return KINDS[kind](body, opts, width, lo, hi)


def hbar(body, opts, width, lo, hi):
    data = _draw.rows(body)
    if not data:
        raise ValueError("no rows")
    show_values = opts.get("values", "on") != "off"
    label_w = max(len(l) for l, _ in data)
    figures = [_draw.fmt(v) for _, v in data]
    figure_w = max(len(f) for f in figures) + 1 if show_values else 0
    bar_w = width - figure_w - (label_w + 2 if label_w else 0)
    if bar_w < 4:
        raise ValueError("too narrow for a bar")
    top = hi if hi is not None else max(v for _, v in data)
    top = top or 1
    lines = []
    for (label, value), figure in zip(data, figures):
        segs = []
        if label_w:
            segs.append((label.ljust(label_w) + "  ", "fg"))
        segs.append((_draw.hbar(value / top, bar_w), "fg"))
        if show_values:
            segs.append((figure.rjust(figure_w), "dim"))
        lines.append(segs)
    return lines


def bar(body, opts, width, lo, hi):
    data = _draw.rows(body)
    if not data:
        raise ValueError("no rows")
    height = int(opts.get("height", 8))
    bar_w = int(opts.get("bar", 3))
    show_values = opts.get("values", "on") != "off"
    n = len(data)
    # columns spread across the width, labels sharing the slot beneath each
    slot = max(bar_w + 1, width // n)
    if slot * n > width:
        raise ValueError(f"{n} bars do not fit in {width} columns")
    top = hi if hi is not None else max(v for _, v in data)
    top = top or 1
    cols = [_draw.vbar(v / top, height) for _, v in data]
    lines = []
    if show_values:
        segs = []
        for _, v in data:
            segs.append((_draw.fmt(v).center(slot), "dim"))
        lines.append(segs)
    for r in range(height):
        row = ""
        for col in cols:
            row += (col[r] * bar_w).center(slot)
        lines.append([(row, "fg")])
    lines.append([("─" * (slot * n), "faint")])
    labels = ""
    for label, _ in data:
        labels += label[:slot - 1].center(slot)
    lines.append([(labels, "dim")])
    return lines


def _axis_labels(lo, hi, height):
    """Left-hand labels: the top and bottom of the scale, blank between."""
    top, bottom = _draw.fmt(hi), _draw.fmt(lo)
    w = max(len(top), len(bottom))
    labels = [""] * height
    labels[0], labels[-1] = top, bottom
    return [l.rjust(w) for l in labels], w


def _plot(points_by_series, opts, width, lo, hi, x_lo=None, x_hi=None):
    """Series of (x, y) points on a braille canvas with an optional axis."""
    height = int(opts.get("height", 8))
    axis = opts.get("axis", "on") != "off"
    ys = [y for s in points_by_series for _, y in s]
    xs = [x for s in points_by_series for x, _ in s]
    lo, hi = _draw.scale(ys, lo, hi)
    x_lo, x_hi = _draw.scale(xs, x_lo, x_hi)

    labels, label_w = _axis_labels(lo, hi, height) if axis else ([""] * height, 0)
    plot_w = width - (label_w + 2 if axis else 0)
    if plot_w < 4:
        raise ValueError("too narrow for a chart")
    canvases = [_draw.Braille(plot_w, height) for _ in points_by_series]
    for canvas, points in zip(canvases, points_by_series):
        dots = [((x - x_lo) / (x_hi - x_lo) * (plot_w * 2 - 1),
                 (y - lo) / (hi - lo) * (height * 4 - 1)) for x, y in points]
        yield canvas, dots
    # merge: a later (dimmer) series never paints over an earlier one
    rendered = [c.render() for c in canvases]
    lines = []
    for r in range(height):
        segs = []
        if axis:
            segs.append((labels[r] + " ", "dim"))
            segs.append(("│", "faint"))
        # per cell, the first series with a dot there wins its tone
        run, run_tone = "", None
        for c in range(plot_w):
            tone = "faint"
            ch = "⠀"
            for s, rows in enumerate(rendered):
                if rows[r][c] != "⠀":
                    ch, tone = rows[r][c], TONES[min(s, 2)]
                    break
            if tone != run_tone and run:
                segs.append((run, run_tone))
                run = ""
            run += ch
            run_tone = tone
        if run:
            segs.append((run, run_tone))
        lines.append(segs)
    if axis:
        lines.append([(" " * (label_w + 1) + "└" + "─" * plot_w, "faint")])
    yield lines


def _run(gen, draw):
    """Drive _plot: it yields each canvas with its dots, then the lines."""
    lines = None
    for item in gen:
        if isinstance(item, tuple):
            draw(*item)
        else:
            lines = item
    return lines


def line(body, opts, width, lo, hi):
    data = series(body)
    if not data:
        raise ValueError("no series")
    points = [[(i, y) for i, y in enumerate(s)] for s in data[:3]]
    longest = max(len(s) for s in data) - 1

    def draw(canvas, dots):
        for (x0, y0), (x1, y1) in zip(dots, dots[1:]):
            canvas.line(x0, y0, x1, y1)
        if len(dots) == 1:
            canvas.dot(*dots[0])

    return _run(_plot(points, opts, width, lo, hi, 0, max(longest, 1)), draw)


def scatter(body, opts, width, lo, hi):
    pts = []
    for s in series(body):
        if len(s) != 2:
            raise ValueError("scatter wants `x y` on each line")
        pts.append(tuple(s))
    if not pts:
        raise ValueError("no points")

    def draw(canvas, dots):
        for d in dots:
            canvas.dot(*d)

    return _run(_plot([pts], opts, width, lo, hi), draw)


def spark(body, opts, width, lo, hi):
    data = series(body)
    if not data:
        raise ValueError("no series")
    lines = []
    for s in data:
        lo_, hi_ = _draw.scale(s, lo, hi)
        row = "".join(_draw.EIGHTHS_V[max(1, int(round((v - lo_) / (hi_ - lo_) * 8)))] for v in s)
        lines.append([(row[:width], "fg")])
    return lines


KINDS = {"hbar": hbar, "bar": bar, "line": line, "scatter": scatter, "spark": spark}
