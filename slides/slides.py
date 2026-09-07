"""slides - markdown to a pdf slide deck, drawn in characters.

A deck is a markdown file with `===` on a line of its own between slides.
Each slide becomes one 16:9 page, set in the terminal's font on a grid of
`columns` characters (72 unless the frontmatter says otherwise), so anything
drawn in characters lines up exactly with the text around it. The pdf lands
next to the source with the same name; tpv, if it has the old one open,
re-renders.

  slides deck.md
  slides deck.md -o out.pdf
  slides deck.md --typ        print the generated typst instead

Frontmatter, all optional:

  ---
  slides: true      what tells the editor to export with this, not pandoc
  theme: dark       or light
  size: 13pt
  columns: 72
  font: JetBrainsMono NFM
  ---

Markdown that is understood: `#` is the slide's title, `##` and deeper a dim
subtitle, paragraphs, `-` and `1.` lists (nested by indenting), `>` quotes,
`![alt](path)` on its own line, and inline **bold**, *emphasis*, `code`,
[links](url). A slide holding only headings is centred vertically. A fenced
block is drawn verbatim, unless its language names a plugin.

Plugins live in plugins/ beside this file; the file's name is the fence
language. One exposes

  def render(body: str, args: list[str], opts: dict[str, str], width: int) -> list

and returns the lines to draw, each a str or a list of (text, tone) pairs,
tone being "fg", "dim" or "faint". `width` is the grid width in characters.
For ```chart bar height=6``` the args are ["bar"] and opts {"height": "6"}.
"""

import argparse
import importlib.util
import os
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TONES = ("fg", "dim", "faint")
DEFAULTS = {"theme": "dark", "size": "13pt", "columns": "72", "font": "JetBrainsMono NFM"}


class DeckError(Exception):
    pass


# --- plugins -----------------------------------------------------------------

def load_plugins():
    plugins = {}
    folder = os.path.join(HERE, "plugins")
    if folder not in sys.path:  # so a plugin can `import _draw`
        sys.path.insert(0, folder)
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".py") or name.startswith("_"):
            continue
        path = os.path.join(folder, name)
        spec = importlib.util.spec_from_file_location("slides_plugin_" + name[:-3], path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, "render"):
            plugins[name[:-3]] = module
    return plugins


def normalise_lines(lines, width, where):
    """A plugin's lines as (text, tone) segment lists, checked against the grid."""
    out = []
    for i, line in enumerate(lines):
        segs = [(line, "fg")] if isinstance(line, str) else [tuple(s) for s in line]
        for text, tone in segs:
            if tone not in TONES:
                raise DeckError(f"{where}: unknown tone {tone!r} (use fg, dim or faint)")
        if sum(len(t) for t, _ in segs) > width:
            print(f"warning: {where}: line {i + 1} is wider than {width} columns and will wrap",
                  file=sys.stderr)
        out.append(segs or [(" ", "fg")])
    return out


# --- typst emission ----------------------------------------------------------

def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


INLINE = re.compile(
    r"\*\*(?P<bold>.+?)\*\*"
    r"|`(?P<code>[^`]+)`"
    r"|(?<!\w)\*(?P<em>[^*]+?)\*(?!\w)"
    r"|(?<!\w)_(?P<em2>[^_]+?)_(?!\w)"
    r"|\[(?P<label>[^\]]+)\]\((?P<url>[^)\s]+)\)"
)


def inline(text):
    """Markdown inline runs as a typst content expression."""
    parts = []
    pos = 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            parts.append(f"text({q(text[pos:m.start()])})")
        if m.group("bold") is not None:
            parts.append(f"text(weight: 800, {q(m.group('bold'))})")
        elif m.group("code") is not None:
            parts.append(f"code({q(m.group('code'))})")
        elif m.group("em") is not None or m.group("em2") is not None:
            parts.append(f"emph(text({q(m.group('em') or m.group('em2'))}))")
        else:
            parts.append(f"link({q(m.group('url'))}, text({q(m.group('label'))}))")
        pos = m.end()
    if pos < len(text):
        parts.append(f"text({q(text[pos:])})")
    return " + ".join(parts) or 'text("")'


def ascii_expr(lines):
    rows = []
    for segs in lines:
        rows.append("(" + ", ".join(f"({q(t)}, {q(tone)})" for t, tone in segs) + ",)")
    return "ascii((" + ", ".join(rows) + ",))"


# --- markdown ----------------------------------------------------------------

FENCE = re.compile(r"^(`{3,}|~{3,})\s*(.*)$")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)(?:\{width=([^}]+)\})?\s*$")
QUOTE = re.compile(r"^>\s?(.*)$")


def frontmatter(text):
    meta = dict(DEFAULTS)
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                body = "\n".join(lines[i + 1:])
                break
            if ":" in lines[i]:
                key, _, value = lines[i].partition(":")
                meta[key.strip()] = value.strip().strip("'\"")
        else:
            raise DeckError("frontmatter never closes")
    else:
        body = text
    return meta, body


def split_slides(body):
    slides, current = [], []
    for line in body.split("\n"):
        if re.match(r"^===+\s*$", line):
            slides.append(current)
            current = []
        else:
            current.append(line)
    slides.append(current)
    return [s for s in slides if any(l.strip() for l in s)]


def parse_list(items):
    """(indent, marker, text) triples as a nested typst list/enum expression."""
    def build(start, depth_indent):
        out, i = [], start
        kind = "enum" if items[start][1][0].isdigit() else "list"
        while i < len(items) and items[i][0] == depth_indent:
            item = inline(items[i][2])
            i += 1
            if i < len(items) and items[i][0] > depth_indent:
                child, i = build(i, items[i][0])
                item = f"{item} + {child}"
            out.append(item)
        return f"{kind}({', '.join(out)})", i

    expr, i = build(0, items[0][0])
    while i < len(items):  # a dedent below the first level: start again
        more, i = build(i, items[i][0])
        expr += " + " + more
    return expr


def parse_slide(lines, plugins, width, number):
    """One slide's lines as a list of typst content expressions."""
    parts = []
    has_title = False
    only_headings = True
    i = 0
    paragraph = []

    def flush():
        if paragraph:
            parts.append(f"par({inline(' '.join(paragraph))})")
            paragraph.clear()

    while i < len(lines):
        line = lines[i]
        fence = FENCE.match(line)
        if fence:
            flush()
            marker, info = fence.groups()
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith(marker):
                body.append(lines[i])
                i += 1
            i += 1  # closing fence
            words = shlex.split(info)
            lang = words[0] if words else ""
            where = f"slide {number}, ```{lang}"
            if lang in plugins:
                args = [w for w in words[1:] if "=" not in w]
                opts = dict(w.split("=", 1) for w in words[1:] if "=" in w)
                try:
                    drawn = plugins[lang].render("\n".join(body), args, opts, width)
                except DeckError:
                    raise
                except Exception as e:  # a plugin's own mistake, named plainly
                    raise DeckError(f"{where}: {type(e).__name__}: {e}") from e
            else:
                drawn = body
            parts.append(ascii_expr(normalise_lines(drawn, width, where)))
            only_headings = False
            continue

        heading = HEADING.match(line)
        if heading:
            flush()
            level, text = heading.groups()
            if len(level) == 1 and not has_title:
                parts.append(f"title({inline(text)})")
                has_title = True
            else:
                parts.append(f"subtitle({inline(text)})")
            i += 1
            continue

        image = IMAGE.match(line)
        if image:
            flush()
            alt, src, w = image.groups()
            parts.append(f"image({q(src)}, width: {w or '100%'}, alt: {q(alt)})")
            only_headings = False
            i += 1
            continue

        if LIST_ITEM.match(line):
            flush()
            items = []
            while i < len(lines) and (m := LIST_ITEM.match(lines[i])):
                indent, marker, text = m.groups()
                items.append([len(indent), marker, text])
                i += 1
                # continuation lines, indented past the marker
                while i < len(lines) and lines[i].strip() and not LIST_ITEM.match(lines[i]) \
                        and len(lines[i]) - len(lines[i].lstrip()) > len(indent):
                    items[-1][2] += " " + lines[i].strip()
                    i += 1
            parts.append(parse_list(items))
            only_headings = False
            continue

        if QUOTE.match(line):
            flush()
            quoted = []
            while i < len(lines) and (m := QUOTE.match(lines[i])):
                quoted.append(m.group(1))
                i += 1
            parts.append(f"quote({inline(' '.join(q_ for q_ in quoted if q_.strip()))})")
            only_headings = False
            continue

        if not line.strip():
            flush()
        else:
            paragraph.append(line.strip())
            only_headings = False
        i += 1

    flush()
    return parts, only_headings


def build(text, plugins):
    meta, body = frontmatter(text)
    try:
        columns = int(meta["columns"])
    except ValueError:
        raise DeckError(f"columns must be a whole number, not {meta['columns']!r}")
    if meta["theme"] not in ("dark", "light"):
        raise DeckError(f"theme must be dark or light, not {meta['theme']!r}")

    out = [
        f"#let cfg = (theme: {q(meta['theme'])}, size: {meta['size']}, "
        f"columns: {columns}, font: {q(meta['font'])})",
    ]
    with open(os.path.join(HERE, "theme.typ"), encoding="utf-8") as f:
        out.append(f.read())
    for n, slide in enumerate(split_slides(body), 1):
        parts, only_headings = parse_slide(slide, plugins, columns, n)
        centred = "true" if only_headings else "false"
        out.append(f"#slide(centred: {centred},\n  " + ",\n  ".join(parts) + ",\n)")
    return "\n".join(out) + "\n"


# --- main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="markdown to a pdf slide deck")
    ap.add_argument("source")
    ap.add_argument("-o", "--output", help="pdf path (default: beside the source)")
    ap.add_argument("--typ", action="store_true", help="print the typst source instead")
    ap.add_argument("--font-path", help="extra font directory for typst")
    args = ap.parse_args()

    with open(args.source, encoding="utf-8") as f:
        text = f.read()
    try:
        typ = build(text, load_plugins())
    except DeckError as e:
        sys.exit(f"slides: {e}")

    if args.typ:
        sys.stdout.write(typ)
        return

    output = os.path.abspath(args.output or os.path.splitext(args.source)[0] + ".pdf")
    cmd = ["typst", "compile", "-", output]
    if args.font_path:
        cmd += ["--font-path", args.font_path]
    # from the deck's own folder, so an image path in it resolves
    proc = subprocess.run(cmd, input=typ.encode("utf-8"), cwd=os.path.dirname(os.path.abspath(args.source)),
                          capture_output=True)
    sys.stderr.write(proc.stderr.decode("utf-8", "replace"))
    if proc.returncode != 0:
        sys.exit(proc.returncode)
    print(f"wrote {os.path.basename(output)}")


if __name__ == "__main__":
    main()
