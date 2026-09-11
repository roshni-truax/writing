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
  heatmap         a grid of values, each cell shaded by how large it is:
                  the first line names the columns, every line after it is
                  a row's name and one number per column

options
  height=8       rows for bar, line and scatter
  width=60       columns, if not the whole grid
  max=100        the top of the scale (min= for the bottom)
  values=false   hide the figures on bar charts
  axis=false     drop the axis and its labels on line and scatter
  bar=3          the width of a column in `bar vertical` (else its widest
                 label)
  size=1         squares a heatmap's cell is drawn from; one square is two
                 characters beside one row
  names=flat     a heatmap's column names written across the top instead of
                 turned a quarter turn
"""

import re
import shlex

import _draw
import frontmatter

from _draw import TONES

BARS = 3  # numbers a bar row may carry


def series(body):
    """Each non-empty line as a list of numbers."""
    out = []
    for line in body.split("\n"):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        out.append([_draw.Number(t) for t in re.split(r"[,\s]+", line) if t])
    return out


def render(body, args, opts, width):
    width = int(opts.get("width", width))
    kind = " ".join(args) or "bar"
    if kind == "bar":
        kind = "bar horizontal"
    if kind not in KINDS:
        raise ValueError(f"unknown chart kind {kind!r}; one of {', '.join(KINDS)}")
    lo = _draw.Number(opts["min"]) if "min" in opts else None
    hi = _draw.Number(opts["max"]) if "max" in opts else None
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
    show_values = frontmatter.switch(opts.get("values", "true"), "values")
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
    show_values = frontmatter.switch(opts.get("values", "true"), "values")
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
        lines.append(_draw.trim_row(segs))
    lines.append([("─" * (slot * n - 1), "faint")])
    labels = ""
    for label, _ in data:
        labels += label[:bar_w].center(slot)
    lines.append([(labels.rstrip(), "dim")])
    return lines


def _axis_labels(lo, hi, height):
    """Left-hand labels: the top and bottom of the scale, blank between."""
    top, bottom = _draw.fmt(hi), _draw.fmt(lo)
    w = max(len(top), len(bottom))
    labels = [""] * height
    labels[0], labels[-1] = top, bottom
    return [l.rjust(w) for l in labels], w


def _plot(points_by_series, draw, opts, width, lo, hi, x_lo=None, x_hi=None):
    """Series of (x, y) points on a braille canvas with an optional axis.

    `draw` is handed each series' canvas and its points in dots, and puts
    them on it however that kind of chart does: a line joins them, a
    scatter marks each one."""
    height = int(opts.get("height", 8))
    axis = frontmatter.switch(opts.get("axis", "true"), "axis")
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
        draw(canvas, dots)
    # merge: a later (dimmer) series never paints over an earlier one
    rendered = [c.render() for c in canvases]
    lines = []
    for r in range(height):
        segs = []
        if axis:
            segs.append((labels[r] + " ", "dim"))
            segs.append(("│", "faint"))
        # per cell, the first series with a dot there wins its tone
        cells = []
        for c in range(plot_w):
            cell = ("⠀", "faint")
            for i, rows in enumerate(rendered):
                if rows[r][c] != "⠀":
                    cell = (rows[r][c], TONES[min(i, 2)])
                    break
            cells.append(cell)
        lines.append(segs + _draw.segments(cells))
    if axis:
        lines.append([(" " * (label_w + 1) + "└" + "─" * plot_w, "faint")])
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

    return _plot(points, draw, opts, width, lo, hi, 0, max(longest, 1))


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

    return _plot([pts], draw, opts, width, lo, hi)


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




# --- heatmap ------------------------------------------------------------------
#
# Every cell is solid, and what changes is the ink: each is mixed its own
# share of the way from the page to the ink the deck is written in, so the
# scale is as near continuous as the mixing is. Shading with ░ ▒ ▓ gave a
# handful of steps and the difference between two of them read as a change
# of texture rather than of quantity; binning those into nine was no better,
# only greyer. The lowest is held off the ground so that a cell at the
# bottom of the scale is still visibly a cell.
FLOOR = 22

# A square, in characters. The row pitch measured against the character
# advance is 2.2 to 1 at any size, so two characters beside one row is as
# near square as this grid comes, and `size` counts squares from there.
SQUARE = 2


def shade(fraction):
    return "█", f"shade-{round(FLOOR + (100 - FLOOR) * fraction)}"


def heatmap(body, opts, width, lo, hi):
    lines = [l for l in body.split("\n") if l.strip() and not l.strip().startswith("//")]
    if len(lines) < 2:
        raise ValueError("a heatmap wants a line of column names and a line for each row")
    columns = shlex.split(lines[0])
    if not columns:
        raise ValueError("the first line names the columns")

    data = _draw.rows("\n".join(lines[1:]), most=len(columns))
    for name, values in data:
        if len(values) != len(columns):
            raise ValueError(f"{len(columns)} columns but {len(values)} numbers on the "
                             f"{name or 'first'} row")

    size = int(opts.get("size", 1))
    if size < 1:
        raise ValueError("a cell is at least one square")
    across = SQUARE * size
    label_w = max(len(name) for name, _ in data)
    indent = label_w + 1 if label_w else 0
    if indent + across * len(columns) > width:
        raise ValueError(f"{len(columns)} cells of {size} do not fit in {width} "
                         f"characters; try a smaller size or `small`")

    every = [v for _, values in data for v in values]
    lo = min(every) if lo is None else lo
    hi = max(every) if hi is None else hi

    def level(v):
        if hi <= lo:
            return 1.0
        return max(0.0, min(1.0, (v - lo) / (hi - lo)))

    out = []
    flat = opts.get("names", "turned") == "flat"
    if flat:
        out.append([(" " * indent + "".join(n[:across].center(across) for n in columns), "dim")])
    for name, values in data:
        shades = [shade(level(v)) for v in values]
        for row in range(size):  # a cell is `size` rows tall as well as wide
            label = name.rjust(label_w) if row == (size - 1) // 2 else " " * label_w
            segs = [(label + " ", "fg")] if indent else []
            segs += [(character * across, tone) for character, tone in shades]
            out.append(segs)

    if flat:
        return out
    return _draw.turned(out, indent, across, columns)


KINDS = {"bar horizontal": hbar, "bar vertical": bar, "line": line, "scatter": scatter,
         "spark": spark, "heatmap": heatmap}
