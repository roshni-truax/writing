"""diagram: text at points, and arrows between them, in the spirit of tikz.

    ```diagram
    (0,1) draft
    (1,1) revision
    (1,0) proof
    (0,1) -> (1,1)
    (1,1) -> (1,0)
    (1,0) <-> (0,1)
    ```

A line beginning with a point and then words puts those words there,
centred on the point. A line of the form (x1,y1) -> (x2,y2) draws an arrow
between the text at those two points; `<->` for both heads, `<-` for the
other way, `-` for a plain line. A point with no text at it can still be an
end, in which case the line runs to the point itself.

The coordinates are only relative: y runs upward, as in tikz, and the grid
is sized here, each column and row spaced as widely as its widest text and
a passing arrow need, while keeping the proportions the coordinates give.
Arrows leave and arrive one cell clear of the text and are routed around
any other text in the way, turning as little as they can.

options
  y=down     y runs downward instead
"""

import heapq
import math
import re


POINT = r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)"
NODE = re.compile(rf"^{POINT}\s+(.+)$")
EDGE = re.compile(rf"^{POINT}\s*(<->|->|<-|-)\s*{POINT}$")

GAP_X = 6   # cells between neighbouring texts: space, line, head, space at least
GAP_Y = 6   # rows between neighbouring texts: room for a shaft between two heads
MARGIN = 4  # free cells around the whole, so an arrow can go round the outside

HEADS = {(0, 1): "▶", (0, -1): "◀", (1, 0): "▼", (-1, 0): "▲"}
# each line character as the set of sides it reaches, so two lines meeting
# in a cell can be merged into the junction that joins them
ARMS = {
    "─": "EW", "│": "NS", "┌": "SE", "┐": "SW", "└": "NE", "┘": "NW",
    "├": "NSE", "┤": "NSW", "┬": "SEW", "┴": "NEW", "┼": "NSEW",
}
JOIN = {frozenset(v): k for k, v in ARMS.items()}
CORNERS = {  # (direction in, direction out) -> the corner that joins them
    ((0, 1), (1, 0)): "┐", ((0, 1), (-1, 0)): "┘",
    ((0, -1), (1, 0)): "┌", ((0, -1), (-1, 0)): "└",
    ((1, 0), (0, 1)): "└", ((1, 0), (0, -1)): "┘",
    ((-1, 0), (0, 1)): "┌", ((-1, 0), (0, -1)): "┐",
}


def render(body, args, opts, width):
    nodes, edges = {}, []
    for line in body.split("\n"):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        m = EDGE.match(line)
        if m:
            a = (float(m.group(1)), float(m.group(2)))
            b = (float(m.group(4)), float(m.group(5)))
            edges.append((a, b, m.group(3)))
            continue
        m = NODE.match(line)
        if m:
            p = (float(m.group(1)), float(m.group(2)))
            if p in nodes:
                raise ValueError(f"two texts at {fmt_point(p)}")
            nodes[p] = m.group(3).strip()
            continue
        raise ValueError(f"cannot read {line!r}: want `(x,y) text` or `(x1,y1) -> (x2,y2)`")
    if not nodes and not edges:
        raise ValueError("nothing to draw")
    for a, b, _ in edges:  # a bare point is a text of nothing
        nodes.setdefault(a, "")
        nodes.setdefault(b, "")

    flip = opts.get("y", "up") == "down"
    col = spread(sorted({p[0] for p in nodes}),
                 lambda x: max(math.ceil(len(t) / 2) for p, t in nodes.items() if p[0] == x),
                 GAP_X)
    ys = sorted({p[1] for p in nodes}, reverse=not flip)
    row = spread(ys, lambda y: 0, GAP_Y)

    # place the text, remembering each one's cells
    boxes = {}
    for p, text in nodes.items():
        c, r = col[p[0]] + MARGIN, row[p[1]] + MARGIN
        left = c - len(text) // 2
        boxes[p] = (r, left, left + len(text) - 1, c)  # row, first col, last col, centre
    height = max(b[0] for b in boxes.values()) + MARGIN + 1
    span = max(b[2] for b in boxes.values()) + MARGIN + 1
    grid = [[(" ", "fg") for _ in range(span)] for _ in range(height)]
    rings = set()  # every text and the one-cell ring around it
    for p, text in nodes.items():
        r, left, right, _ = boxes[p]
        for i, ch in enumerate(text):
            grid[r][left + i] = (ch, "fg")
        if text:
            for rr in range(r - 1, r + 2):
                for cc in range(left - 1, right + 2):
                    rings.add((rr, cc))

    blocked = set(rings)  # rings, and then every arrowhead drawn
    used = set()          # every cell a line has been drawn in
    taken = set()         # (point, direction) of every side a line already uses
    for a, b, kind in edges:
        draw_edge(grid, rings, blocked, used, boxes, nodes, a, b, kind, height, span, taken)

    return trim([segments(r) for r in grid])


def fmt_point(p):
    return "(" + ",".join(str(int(v)) if v == int(v) else str(v) for v in p) + ")"


def spread(values, half, gap):
    """Cell positions for sorted coordinate values: one scale for all of
    them, the smallest that leaves every neighbouring pair room."""
    if len(values) == 1:
        return {values[0]: half(values[0])}
    scale = 0.0
    for a, b in zip(values, values[1:]):
        need = half(a) + half(b) + gap
        scale = max(scale, need / abs(b - a))
    origin = values[0]
    return {v: half(values[0]) + round(abs(v - origin) * scale) for v in values}


def port(box, text, horizontal, towards_right, towards_down):
    """Where a line meets a text: the cell one clear of its ring on the side
    that faces the other end, and the direction pointing away from the text."""
    r, left, right, c = box
    out = 2 if text else 0
    if horizontal:
        return ((r, right + out), (0, 1)) if towards_right else ((r, left - out), (0, -1))
    return ((r + out, c), (1, 0)) if towards_down else ((r - out, c), (-1, 0))


def draw_edge(grid, rings, blocked, used, boxes, nodes, a, b, kind, height, span, taken):
    ra, la, rga, ca = boxes[a]
    rb, lb, rgb, cb = boxes[b]
    horizontal = abs(cb - ca) > abs(rb - ra)

    def choose(p):
        # the side facing the other end. when a line already uses that side,
        # the other axis: the side facing the other end if it lies that way
        # at all, otherwise below or to the right; and when that is used too,
        # the first side is shared
        box, text = boxes[p], nodes[p]
        right = (cb > ca) == (p == a) if cb != ca else True
        down = (rb > ra) == (p == a) if rb != ra else True
        cell, d = port(box, text, horizontal, right, down)
        if (p, d) in taken:
            alt, ad = port(box, text, not horizontal, right, down)
            if (p, ad) not in taken:
                cell, d = alt, ad
        taken.add((p, d))
        return cell, d

    start, sdir = choose(a)
    end, edir = choose(b)
    for cell, p in ((start, a), (end, b)):
        if cell in rings and nodes[p]:
            raise ValueError(f"no room for a line at {fmt_point(p)}: something else is too close")
    # the line leaves and arrives straight, so the route runs between the
    # cells one further out along each port's axis
    s_out = (start[0] + sdir[0], start[1] + sdir[1])
    e_out = (end[0] + edir[0], end[1] + edir[1])
    if start == end:
        path = [start]
    elif abs(end[0] - start[0]) + abs(end[1] - start[1]) < 3 or s_out == end or e_out == start:
        # too close for the straight run-in: the ports join directly
        path = route(start, end, blocked, used, height, span)
    else:
        # the ports themselves are out of bounds to the route, so it cannot
        # double back through one
        middle = route(s_out, e_out, blocked | {start, end}, used, height, span)
        path = None if middle is None else [start] + middle + [end]
    if path is None:
        raise ValueError(f"no route from {fmt_point(a)} to {fmt_point(b)}")
    path = [c for i, c in enumerate(path) if i == 0 or c != path[i - 1]]

    dirs = [(n[0] - p[0], n[1] - p[1]) for p, n in zip(path, path[1:])]
    for i, cell in enumerate(path):
        into = dirs[i - 1] if i > 0 else sdir
        out = dirs[i] if i < len(dirs) else (-edir[0], -edir[1])
        if i == len(path) - 1 and kind in ("->", "<->"):
            ch = HEADS[(-edir[0], -edir[1])]
        elif i == 0 and kind in ("<-", "<->"):
            ch = HEADS[(-sdir[0], -sdir[1])]
        elif into != out:
            ch = CORNERS.get((into, out), "┼")
        else:
            ch = "─" if into[0] == 0 else "│"
        r, c = cell
        have = grid[r][c][0]
        if have in ARMS and ch in ARMS:
            ch = JOIN[frozenset(ARMS[have]) | frozenset(ARMS[ch])]  # lines meeting
        elif have in HEADS.values() and ch not in HEADS.values():
            ch = have  # a head stays a head when a line shares its cell
        grid[r][c] = (ch, "dim")
        used.add(cell)
        if ch in HEADS.values():
            blocked.add(cell)  # a head is not to be drawn through


def route(start, end, blocked, used, height, span):
    """A* over the free cells, four ways. Turning costs more than going on,
    and a cell another line already runs through costs more still, so a
    path bends as little as it can and keeps to itself where it can."""
    if start == end:
        return [start]
    frontier = [(0, 0, start, None, None)]
    best = {}
    parent = {}
    counter = 0
    while frontier:
        f, g, cell, d, prev = heapq.heappop(frontier)
        if cell in best and best[cell] <= g:
            continue
        best[cell] = g
        parent[cell] = prev
        if cell == end:
            path = []
            while cell is not None:
                path.append(cell)
                cell = parent[cell]
            return path[::-1]
        for nd in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            n = (cell[0] + nd[0], cell[1] + nd[1])
            if not (0 <= n[0] < height and 0 <= n[1] < span):
                continue
            if n in blocked and n != end:
                continue
            cost = g + 1 + (4 if d is not None and nd != d else 0) + (6 if n in used else 0)
            h = abs(end[0] - n[0]) + abs(end[1] - n[1])
            counter += 1
            heapq.heappush(frontier, (cost + h, cost, n, nd, cell))
    return None


def segments(row):
    segs, run, tone = [], "", None
    for ch, t in row:
        if t != tone and run:
            segs.append((run, tone))
            run = ""
        run += ch
        tone = t
    if run:
        segs.append((run, tone))
    return segs


def trim(lines):
    """Drop the margin: empty rows top and bottom, empty columns left."""
    def blank(segs):
        return all(not t.strip() for t, _ in segs)
    while lines and blank(lines[0]):
        lines.pop(0)
    while lines and blank(lines[-1]):
        lines.pop()
    lead = min(len("".join(t for t, _ in segs)) - len("".join(t for t, _ in segs).lstrip())
               for segs in lines)
    out = []
    for segs in lines:
        cut = lead
        new = []
        for t, tone in segs:
            if cut >= len(t):
                cut -= len(t)
                continue
            new.append((t[cut:], tone))
            cut = 0
        text = "".join(t for t, _ in new).rstrip()
        # trim the right edge too, keeping the segment tones
        kept, n = [], 0
        for t, tone in new:
            if n >= len(text):
                break
            kept.append((t[: len(text) - n], tone))
            n += len(t)
        out.append(kept or [(" ", "fg")])
    return out
