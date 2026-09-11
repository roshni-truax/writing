#!/usr/bin/env python3
"""printer - markdown to a pdf.

One command for every pdf this repo makes. A manuscript becomes an A5 page
set in the terminal's own type; a deck - anything whose frontmatter says
`slides: true` - goes to slides/ beside this file, which sets it 16:9 on a
character grid. Either way the pdf lands next to the source with the same
name, and the viewer, if it has the old one open, notices and re-renders.

  printer file.md
  printer file.md -o out.pdf

Both kinds open with the same frontmatter: a fenced block on the first line,
`key: value` a line at a time. Prose reads

  theme: light          or dark; the grounds and inks the deck half uses
  skip-numbering: 1     that many opening pages carry no number, and the
                        count starts after them, so with 1 the second page
                        is "1"
  papersize: a5
  fontsize: 10pt
  linestretch: 1.15
  margin:               horizontal, vertical, top, bottom, left, right
    horizontal: 1.6cm

Beyond markdown itself, prose reads:

  a blank line          the ordinary paragraph break
  each one after        a line of air, one line of the body's leading
  ---                   a scene break: a short faded stroke, not a rule
  ##                    a chapter, with a pause under it; # is the book
  > a quotation         footnote-sized, behind a hairline at its left

and two fenced blocks, which take no body:

  ``` pagebreak         start a new page here
  ``` image="map.png"   the image, centered, at the width of the text block
  ``` image="map.png" size=0.6      six tenths of that width
  ``` image="map.png" size=full     alone on a page of its own

A deck's own additions are in slides/slides.py; the whole of both is written
out in SYNTAX.md beside this file.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))  # through the symlink on the nas
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "slides"))

import frontmatter  # noqa: E402  (found through the path set just above)
import references  # noqa: E402
import slides  # noqa: E402

LEADING = 1.15  # the body's line height, so a line of air is one line tall
PALETTE = os.path.join(os.path.dirname(HERE), "palette", "zenwritten.json")
# typst names the margins it takes; these are the words a document uses
MARGINS = {"horizontal": "x", "vertical": "y", "top": "top",
           "bottom": "bottom", "left": "left", "right": "right"}
BLOCK = re.compile(r"^(`{3,}|~{3,})\s*(.*)$")
# a citation or a note, and not one whose braces were escaped
CITE = re.compile(r"(?<!\\)\{\{(.*?)\}\}", re.S)
HANGING = "1.5em"  # the indent a bibliography entry's later lines take


class PrintError(Exception):
    pass


def palette(name):
    """The grounds and inks of one theme, as typst source."""
    try:
        with open(PALETTE, encoding="utf-8") as f:
            themes = json.load(f)
    except OSError as e:
        raise PrintError(f"cannot read the palette at {PALETTE}: {e}")
    if name not in themes:
        known = ", ".join(k for k in themes if not k.startswith("_"))
        raise PrintError(f"theme must be one of {known}, not {name!r}")
    return themes[name]


def blocks(lines, sources=None):
    """The fenced blocks prose reads, as raw typst.

    Each takes no body, so the fence is opened and closed with nothing
    between: what it does is all on the opening line. Anything else fenced
    is left exactly as it is, code included.
    """
    out, i, n = [], 0, len(lines)
    while i < n:
        m = BLOCK.match(lines[i])
        info = shlex.split(m.group(2)) if m else []
        word = info[0].split("=", 1)[0] if info else ""
        if m and word in ("pagebreak", "image", "references"):
            marker = m.group(1)
            body, i = [], i + 1
            while i < n and not lines[i].startswith(marker[0] * 3):
                body.append(lines[i])
                i += 1
            i += 1  # the closing fence
            if any(l.strip() for l in body):
                raise PrintError(f"a ``` {word} block takes nothing inside it")
            if word == "references":
                out += bibliography(sources)
            else:
                out += ["```{=typst}", typst_block(word, info), "```", ""]
            continue
        if m:  # some other fenced block: copied through, fence and all
            marker = m.group(1)
            out.append(lines[i])
            i += 1
            while i < n and not lines[i].startswith(marker[0] * 3):
                out.append(lines[i])
                i += 1
            if i < n:
                out.append(lines[i])
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return out


def cited(lines, sources):
    """The body with every `{{…}}` turned into a footnote.

    A note whose first word is a key in the references is a citation, and
    Chicago decides what it says from what has been cited already; anything
    else is a note in the writer's own words. Code is left alone, the same
    way the blocks above leave it alone, and `\\{{` is how to write the
    braces themselves.
    """
    out, fence = [], None
    for line in lines:
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        mark = m.group(1) if m else None
        if fence:
            if mark and mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
            out.append(line)
            continue
        if mark:
            fence = mark
            out.append(line)
            continue
        out.append(CITE.sub(lambda m: footnote(m.group(1), sources), line)
                   .replace("\\{{", "{{"))
    return out


def footnote(inside, sources):
    inside = inside.strip()
    key = inside.split(",")[0].strip()
    if sources and sources.has(key):
        parts = [p.strip() for p in inside.split(",", 2)]
        locator = parts[1] if len(parts) > 1 else ""
        remark = parts[2] if len(parts) > 2 else ""
        return "^[" + sources.cite(key, locator, remark) + "]"
    return "^[" + inside + "]"


def bibliography(sources):
    """The sources cited, alphabetical, each hanging under its first line."""
    if not sources or not sources.used:
        raise PrintError("a ```references block with nothing cited above it")
    out = ["```{=typst}", f"#set par(hanging-indent: {HANGING})", "```", ""]
    for entry in sources.bibliography():
        out += [entry, ""]
    return out + ["```{=typst}", "#set par(hanging-indent: 0em)", "```", ""]


def typst_block(word, info):
    opts = dict(w.split("=", 1) for w in info if "=" in w)
    if word == "pagebreak":
        if len(info) > 1:
            raise PrintError("a ``` pagebreak block takes no options")
        return "#pagebreak()"
    path = opts.get("image")
    if not path:
        raise PrintError('an image block wants image="the file"')
    size = opts.get("size", "1")
    if size == "full":
        return f"#imagepage({q(path)})"
    try:
        width = float(size)
    except ValueError:
        raise PrintError(f"size is a number or full, not {size!r}")
    if not 0 < width <= 1:
        raise PrintError(f"size runs from just above 0 to 1, not {size}")
    return f"#imageblock({q(path)}, {width * 100:g}%)"


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def spaced(lines):
    """The text with its blank lines kept.

    Markdown collapses any run of blank lines into one paragraph break, so
    each one past the first is turned into a line of air: a raw typst block,
    which pandoc hands to the typesetter untouched. `#v` adds to the
    paragraph spacing rather than replacing it (measured), so two blank
    lines read as the usual gap plus one empty line. A run at the top or
    bottom of the file is dropped, and code keeps its own blanks.
    """
    out, i, n = [], 0, len(lines)
    fence, seen = None, False
    while i < n:
        line = lines[i]
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        mark = m.group(1) if m else None
        if fence:
            out.append(line)
            if mark and mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
            i += 1
        elif mark:
            fence, seen = mark, True
            out.append(line)
            i += 1
        elif not line.strip():
            j = i
            while j < n and not lines[j].strip():
                j += 1
            # an indented code block spans its own blank lines; leave those be
            indented = (j < n and lines[j].startswith("    ")
                        and bool(out) and out[-1].startswith("    "))
            out.append("")
            if j - i > 1 and seen and j < n and not indented:
                out.append("```{=typst}")
                out.append(f"#v({(j - i - 1) * LEADING:.2f}em)")
                out.append("```")
                out.append("")
            i = j
        else:
            seen = True
            out.append(line)
            i += 1
    return out


def metadata(meta):
    """The page settings as a yaml file for pandoc: meta.yaml's defaults
    with the document's own on top.

    Pandoc's typst template hands `margin` straight to typst, which knows x
    and y rather than horizontal and vertical, so the words are translated
    on the way through and nothing anyone edits has to know them.
    """
    with open(os.path.join(HERE, "meta.yaml"), encoding="utf-8") as f:
        page = frontmatter.parse(f.read().split("\n"))
    margins = dict(page.get("margin") or {}, **(meta.get("margin") or {}))
    meta = dict(page, **meta)
    meta["margin"] = margins
    lines = []
    for key in ("papersize", "fontsize", "linestretch"):
        if key in meta:
            lines.append(f"{key}: {meta[key]}")
    margin = meta.get("margin")
    if margin:
        if not isinstance(margin, dict):
            raise PrintError("margin takes indented lines: horizontal, vertical, "
                             "top, bottom, left or right")
        unknown = [k for k in margin if k not in MARGINS]
        if unknown:
            raise PrintError(f"margin has no {' or '.join(unknown)}; it takes "
                             f"{', '.join(MARGINS)}")
        lines.append("margin:")
        for key, value in margin.items():
            lines.append(f"  {MARGINS[key]}: {value}")
    return "\n".join(lines) + "\n" if lines else ""


def read_sources(source, meta):
    """The document's sources: references.json beside it unless the
    frontmatter names another file, and none at all if neither is there."""
    named = meta.get("references")
    beside = os.path.join(os.path.dirname(os.path.abspath(source)), "references.json")
    if named:
        path = os.path.join(os.path.dirname(os.path.abspath(source)), str(named))
        if not os.path.exists(path):
            raise PrintError(f"no references file at {named}")
    elif os.path.exists(beside):
        path = beside
    else:
        return None
    return references.Sources(references.load(path))


def prose(source, output, meta, body):
    """A manuscript as an A5 pdf, through pandoc."""
    output = os.path.abspath(output or os.path.splitext(source)[0] + ".pdf")
    theme = palette(meta.get("theme", "light"))
    lines = body.split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # the newline a file ends with is not a blank line
    # the citations first: a ```references block lists what they used, so it
    # cannot be set until every one of them has been read
    sources = read_sources(source, meta)
    lines = blocks(cited(lines, sources), sources)
    skip = meta.get("skip-numbering")
    if skip is not None:
        # the same raw block the document used to carry itself
        if not str(skip).isdigit():
            raise PrintError(f"skip-numbering is a whole number, not {skip!r}")
        lines = ["```{=typst}", f"#skip-numbering({skip})", "```", ""] + lines
    text = "\n".join(spaced(lines)) + "\n"

    with tempfile.TemporaryDirectory() as tmp:
        # the theme, ahead of header.typ, which sets the page from it
        ground = os.path.join(tmp, "ground.typ")
        with open(ground, "w", encoding="utf-8") as f:
            f.write("\n".join(f'#let {k} = rgb("{v}")' for k, v in theme.items()
                              if k in ("bg", "fg", "dim", "faint")) + "\n")
        cmd = [
            "pandoc",
            "--output=" + output,
            "--pdf-engine=typst",
            # An image on its own line is just an image. Pandoc's default is
            # to promote it to a numbered figure and reprint the alt text
            # underneath as a caption, which reads as "Figure 1: ..." in the
            # pdf. The alt text survives this as alt text; it just stops
            # being printed.
            "-f", "markdown-implicit_figures",
            # code blocks, should any appear, stay greyscale
            "--syntax-highlighting=monochrome",
            "--include-in-header=" + ground,
            "--include-in-header=" + os.path.join(HERE, "header.typ"),
        ]
        # the page, as one file: it has to be a file because the margins
        # are nested, and pandoc's -V flags cannot express nesting - dotted
        # names like margin.x are accepted silently and then never reach
        # the template
        page = os.path.join(tmp, "page.yaml")
        with open(page, "w", encoding="utf-8") as f:
            f.write(metadata(meta))
        cmd.insert(-3, "--metadata-file=" + page)
        # from the manuscript's own directory, not wherever this was
        # started: an image block resolves against the intermediate .typ
        # file, which lands in the pandoc process's cwd.
        proc = subprocess.run(cmd, input=text.encode("utf-8"),
                              cwd=os.path.dirname(os.path.abspath(source)),
                              capture_output=True)
    stderr = proc.stderr.decode("utf-8", "replace")
    if proc.returncode != 0:
        raise PrintError(stderr.rstrip())
    sys.stderr.write(stderr)
    return output


def main():
    # Two arguments and no more: a file, and where to put the pdf. The deck
    # builder keeps its own flags for anyone changing the typst it writes -
    # `slides/slides.py --typ` prints that instead of setting it - and they
    # stay there rather than on the command a manuscript is printed with.
    ap = argparse.ArgumentParser(description="markdown to a pdf")
    ap.add_argument("source")
    ap.add_argument("-o", "--output", help="pdf path (default: beside the source)")
    args = ap.parse_args()

    try:
        with open(args.source, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        sys.exit(f"printer: cannot read {args.source}: {e}")

    try:
        meta, body = frontmatter.read(text)
        if frontmatter.flag(meta, "slides"):
            output = slides.render(args.source, meta, body, args.output)
        else:
            output = prose(args.source, args.output, meta, body)
    except (PrintError, slides.DeckError, frontmatter.FrontmatterError,
            references.ReferenceError) as e:
        sys.exit(f"printer: {e}")
    if output:
        print(f"wrote {os.path.basename(output)}")


if __name__ == "__main__":
    main()
