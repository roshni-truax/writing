"""chart: a chart drawn in characters. The first argument is the kind.

    ```chart bar
    fiction     42
    philosophy  17
    letters      3
    ```

Up to three numbers may follow a label. The bars are then drawn one over
another rather than side by side, the shortest in front, so each colour
owns the stretch where its bar is the shortest one covering it: the first
number in the text's own ink, the second and third a step and two steps
fainter. Written against a target, `41200 40000` fills to the target in the
fainter ink and shows the overshoot in the brighter one.

kinds
  bar             `label value` rows, a bar to the right of each label;
                  the same as `bar horizontal`
  bar vertical    the same rows as upright columns with the labels beneath
  line            one series of numbers per line, comma or space separated,
                  drawn in braille dots; up to three series, each a step
                  dimmer
  scatter         `x y` rows as braille dots
  spark           one series as a single row of ▁▂▃▄▅▆▇█

options
  height=8       rows for bar, line and scatter
  width=60       columns, if not the whole grid
  max=100        the top of the scale (min= for the bottom)
  values=off     hide the figures on bar charts
  axis=off       drop the axis and its labels on line and scatter
  bar=3          the width of a column in `bar vertical` (else its widest
                 label)
"""

import re

import _draw

TONES = ("fg", "dim", "faint")
BARS = 3  # numbers a bar row may carry


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
    kind = " ".join(args) or "bar"
    if kind == "bar":
        kind = "bar horizontal"
    if kind not in KINDS:
        raise ValueError(f"unknown chart kind {kind!r}; one of {', '.join(KINDS)}")
    lo = _draw.number(opts["min"]) if "min" in opts else None
    hi = _draw.number(opts["max"]) if "max" in opts else None
    return KINDS[kind](body, opts, width, lo, hi)


def figure_columns(data, show_values):
    """The printed numbers per row, and the width each column needs."""
    if not show_values:
        return [], []
    figures = [[_draw.fmt(v) for v in values] for _, values in data]
    widths = [max(len(f[k]) for f in figures) for k in range(len(figures[0]))]
    return figures, widths


def hbar(body, opts, width, lo, hi):
    data = _draw.rows(body, most=BARS)
    if not data:
        raise ValueError("no rows")
    show_values = opts.get("values", "on") != "off"
    label_w = max(len(l) for l, _ in data)
    figures, fig_w = figure_columns(data, show_values)
    figure_w = sum(w + 1 for w in fig_w)
    bar_w = width - figure_w - (label_w + 2 if label_w else 0)
    if bar_w < 4:
        raise ValueError("too narrow for a bar")
    top = hi if hi is not None else max(max(values) for _, values in data)
    top = top or 1
    lines = []
    for n, (label, values) in enumerate(data):
        segs = []
        if label_w:
            segs.append((label.ljust(label_w) + "  ", "fg"))
        segs.extend(_draw.nested_h(values, top, bar_w, TONES))
        for k, w in enumerate(fig_w):
            # one series' figures stay dim, as the quieter half of the row;
            # several take their own bar's ink, which is what ties them
            tone = "dim" if len(fig_w) == 1 else TONES[k]
            segs.append((" " + figures[n][k].rjust(w), tone))
        lines.append(segs)
    return lines


def bar(body, opts, width, lo, hi):
    data = _draw.rows(body, most=BARS)
    if not data:
        raise ValueError("no rows")
    height = int(opts.get("height", 8))
    show_values = opts.get("values", "on") != "off"
    n = len(data)
    figures, fig_w = figure_columns(data, show_values)
    # a column is as wide as its widest label or figure (three at least, or
    # `bar=`), with one space between columns; the chart hugs the left margin
    bar_w = int(opts["bar"]) if "bar" in opts else max(
        3, max(len(l) for l, _ in data), max(fig_w or [0]))
    slot = bar_w + 1
    if slot * n - 1 > width:
        raise ValueError(f"{n} bars do not fit in {width} columns")
    top = hi if hi is not None else max(max(values) for _, values in data)
    top = top or 1
    cols = [_draw.nested_v(values, top, height, TONES) for _, values in data]
    lines = []
    # a line of figures per series, above the columns, each in its bar's ink
    for k, w in enumerate(fig_w):
        tone = "dim" if len(fig_w) == 1 else TONES[k]
        row = "".join(figures[i][k][:bar_w].center(slot) for i in range(n))
        lines.append([(row.rstrip(), tone)])
    for r in range(height):
        segs = []
        for col in cols:
            ch, tone = col[r]
            segs.append((ch * bar_w, tone))
            segs.append((" ", "fg"))
        lines.append(trim_right(segs))
    lines.append([("─" * (slot * n - 1), "faint")])
    labels = ""
    for label, _ in data:
        labels += label[:bar_w].center(slot)
    lines.append([(labels.rstrip(), "dim")])
    return lines


def trim_right(segs):
    """The same segments with the trailing blank ones dropped."""
    while segs and not segs[-1][0].strip():
        segs.pop()
    return segs or [(" ", "fg")]


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


KINDS = {"bar horizontal": hbar, "bar vertical": bar, "line": line, "scatter": scatter,
         "spark": spark}
