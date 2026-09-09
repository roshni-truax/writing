"""heatmap: a grid of values, each shaded by how large it is.

    ```heatmap
                mon tue wed thu fri
    morning      3   5   2   8   1
    afternoon    1   0   4   6   2
    evening      7   3   0   2   5
    ```

The first line names the columns; every line after it is a row's name and
one number per column. Quote a name that has a space in it, or that ends in
a number. Nothing has to line up: the spacing above is for the writer, not
for this.

The column names are set above the grid turned a quarter turn, since a
column is only a few characters wide and the names would otherwise run into
each other. The row names stay flat at the left, where there is room for
them: a row is one character tall, so a name turned there would have
nowhere to go.

`size` is how big a cell is drawn, counted in squares. One square is two
characters beside one row, which is as near square as this grid comes, so
`size=3` is nine of them and gives the column names more room to stand in.

options
  size=1        how many squares across and down each cell is drawn
  min=  max=    the ends of the scale, if not the smallest and largest
  names=flat    column names written across the top instead of turned
"""

import shlex

import _draw

# Every cell is solid, and what changes is the ink. Shading with ░ ▒ ▓ gave
# only a handful of steps, and the difference between two of them read as a
# change of texture rather than of quantity. A solid cell mixed a percentage
# of the way from the page to its ink gives as many steps as are worth
# telling apart, and the field reads as one surface. The lowest is held off
# the ground so an empty-looking cell is still a cell.
SHADES = 9
FLOOR = 22


def shade(step):
    at = FLOOR + (100 - FLOOR) * step / (SHADES - 1)
    return "█", f"shade-{round(at)}"

# A square, in characters. The row pitch measured against the character
# advance is 2.2 to 1 at any size, so two characters beside one row is as
# near square as this grid comes, and `size` counts squares from there.
SQUARE = 2


def render(body, args, opts, width):
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
    lo = _draw.number(opts["min"]) if "min" in opts else min(every)
    hi = _draw.number(opts["max"]) if "max" in opts else max(every)

    def level(v):
        if hi <= lo:
            return SHADES - 1
        step = int((v - lo) / (hi - lo) * SHADES)
        return max(0, min(SHADES - 1, step))

    out = []
    if opts.get("names", "turned") == "flat":
        out.append([(" " * indent + "".join(n[:across].center(across) for n in columns), "dim")])
    for name, values in data:
        shades = [shade(level(v)) for v in values]
        for row in range(size):  # a cell is `size` rows tall as well as wide
            label = name.rjust(label_w) if row == (size - 1) // 2 else " " * label_w
            segs = [(label + " ", "fg")] if indent else []
            segs += [(character * across, tone) for character, tone in shades]
            out.append(segs)

    if opts.get("names", "turned") == "flat":
        return out
    return {"lines": out, "turned": {"indent": indent, "step": across, "names": columns}}
