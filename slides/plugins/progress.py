"""progress: a bar filled to a fraction.

    ```progress 0.6
    chapter three
    ```

The fraction is the first argument (0.6, 60%, or 3/5) and the body, if any,
is the label. Several bars share one block when the body has `label value`
lines instead and no argument is given:

    ```progress
    draft    100%
    revision 3/5
    proof    0
    ```

Options: `percent=off` hides the figure, `style=line` draws with ━ and ─
instead of █ and ░, `width=40` narrows the block.
"""

import _draw

STYLES = {"block": ("█", "░"), "line": ("━", "─")}


def render(body, args, opts, width):
    width = int(opts.get("width", width))
    show_percent = opts.get("percent", "on") != "off"
    filled, empty = STYLES[opts.get("style", "block")]

    if args:
        bars = [(body.strip(), _draw.number(args[0]))]
    else:
        bars = _draw.rows(body)
    if not bars:
        raise ValueError("nothing to draw: give a fraction or `label value` lines")

    label_w = max(len(label) for label, _ in bars)
    figure_w = 5 if show_percent else 0  # "  60%" at most
    bar_w = width - figure_w - (label_w + 2 if label_w else 0)
    if bar_w < 4:
        raise ValueError("too narrow for a bar")

    lines = []
    for label, fraction in bars:
        fraction = max(0.0, min(1.0, fraction))
        n = int(round(fraction * bar_w))
        segs = []
        if label_w:
            segs.append((label.ljust(label_w) + "  ", "fg"))
        segs.append((filled * n, "fg"))
        segs.append((empty * (bar_w - n), "faint"))
        if show_percent:
            segs.append((f"{int(round(fraction * 100))}%".rjust(figure_w), "dim"))
        lines.append(segs)
    return lines
