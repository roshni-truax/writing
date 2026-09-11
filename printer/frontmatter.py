"""The block at the top of a document that says how it is set.

Both kinds of document open the same way: a fenced block on the very first
line, holding `key: value` a line at a time.

    ```
    theme: dark
    slides: true
    ```

A key with nothing after the colon takes the indented lines under it, which
is how the margins are given. Nothing else nests. A blank line is skipped
and so is a comment, `#` or `//`. A file that does not open with a fence has
no frontmatter and is all body.

printer/meta.yaml is the same shape, holding the page a manuscript gets
before it says anything, so both are read by `parse` below.
"""

import re

FENCE = re.compile(r"^(`{3,}|~{3,})\s*$")
TRUTH = {"true": True, "false": False}


class FrontmatterError(Exception):
    pass


def read(text):
    """(meta, body): what the block said, and the document after it."""
    lines = text.split("\n")
    if not lines or not FENCE.match(lines[0]):
        return {}, text
    marker = FENCE.match(lines[0]).group(1)
    for i in range(1, len(lines)):
        if lines[i].startswith(marker[0] * 3):
            return parse(lines[1:i]), "\n".join(lines[i + 1:])
    raise FrontmatterError("the frontmatter block never closes")


def parse(lines):
    meta, under = {}, None
    for line in lines:
        if not line.strip() or line.strip().startswith(("//", "#")):
            continue
        indented = line[:1].isspace()
        if ":" not in line:
            raise FrontmatterError(f"the frontmatter wants `key: value`, not {line.strip()!r}")
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip().strip("'\"")
        if indented:
            if under is None:
                raise FrontmatterError(f"{key!r} is indented under nothing")
            meta[under][key] = value
        elif value:
            meta[key], under = value, None
        else:
            meta[key] = {}
            under = key
    return meta


def flag(meta, key, default=False):
    """A frontmatter switch. true and false, and nothing else."""
    if key not in meta:
        return default
    value = str(meta[key]).lower()
    if value not in TRUTH:
        raise FrontmatterError(f"{key} is true or false, not {meta[key]!r}")
    return TRUTH[value]


def switch(value, where):
    """The same, for a `key=value` on a fence line."""
    if str(value).lower() not in TRUTH:
        raise ValueError(f"{where} is true or false, not {value!r}")
    return TRUTH[str(value).lower()]
