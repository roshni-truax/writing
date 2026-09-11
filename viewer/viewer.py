"""viewer - a pdf viewer that runs in the terminal.

Rolled here because nothing else runs on Windows: every existing terminal
pdf viewer leans on unix plumbing (pixel-size ioctls, shared memory) that
never grew a Windows half. This one doesn't. Pages are rasterised by
pdfium - the renderer inside Chrome, shipped as a prebuilt wheel - and
drawn with the iTerm2 inline-image escape, the one image protocol this
wezterm renders on Windows: one escape per frame, wrapped in a
synchronized update so every frame lands whole. It runs on Linux too,
over ssh from the same terminal: only the keyboard half differs, and the
frames travel as they are.

The document is one continuous scroll, the way a manuscript reads, not a
stack of screens. The pdf is read into memory and the file handle released
at once, so an export can overwrite the file while it is on screen; the
viewer notices the change and quietly re-renders. That is the loop this
exists for: manuscript on the left, its pdf on the right, refreshing itself.

  viewer file.pdf
  viewer -s file.pdf  slideshow: one page at a time, whole, centred

  j / k            a line or two down / up; counts work (5j)
                   in slideshow, a whole page down / up
  ctrl-j / ctrl-k  down / up a full page; counts work
  gg  XXgg  G      start / page XX / end
  z / x            zoom out / in (not in slideshow: the fit is the mode)
  Z / X            zoom until the whole page fits / its width fills
  r                reload the file
  q                quit

  click and drag   select the words dragged over
  y                copy what is selected, as paragraphs rather than as the
                   lines the page broke them into
  esc              let the selection go

The clipboard is the terminal's, reached with OSC 52: the text goes out as
an escape and wezterm puts it on the desktop's clipboard, which is the only
way across ssh without something installed at this end.
"""

import base64
import bisect
import io
import json
import os
import re
import shutil
import sys
import threading
import time

# ctypes everywhere, msvcrt only where there is one: the console structures
# below are then defined on every platform, so a mistake in them - a name a
# nested class could not see, say - is found by reading this file anywhere
# rather than only on Windows, where it is hardest to go and look.
import ctypes

if os.name == "nt":
    import msvcrt
else:
    import select
    import termios
    import tty

import pypdfium2 as pdfium
from PIL import Image, ImageChops

ESC = "\x1b"
# what the terminal sends for the mouse, once asked: button, column, row,
# and M for a press or a drag against m for a release
MOUSE = re.compile(r"\x1b\[<(\d+);(\d+);(\d+)([Mm])")
MOUSE_ON = f"{ESC}[?1002h{ESC}[?1006h"   # drags reported, in SGR coordinates
MOUSE_OFF = f"{ESC}[?1006l{ESC}[?1002l"
# The terminal's cell, in px: measured against the repo's wezterm font
# (13pt JetBrains Mono at 1.15 line height). Off-estimates only stretch
# the page slightly; they never lose it.
CELL_W, CELL_H = 9, 20.3
OVERSAMPLE = 2          # render up to twice the guess; scaling down stays crisp
MAX_CANVAS = 4_000_000  # px budget per frame; the oversample yields to it
GAP = 12                # the breath between pages, in pdf points
LINE = 2                # rows of the terminal one j or k scrolls by

# The theme's colours, generated beside the rest of it by
# nvim/lua/zenwritten_compile.lua. Only the status line's ink is wanted here,
# and it is kept there rather than copied here, where a recompile would leave
# it behind.
PALETTE = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                       "palette", "zenwritten.json")
FALLBACK = (128, 128, 128)  # a neutral grey, if the palette cannot be read

def theme(appearance=None):
    # The status line's faded ink. On Windows the appearance is read the same
    # way neovim reads it: from the file wezterm writes it to (see
    # wezterm/wezterm.lua), because the OSC query for the background never
    # survives Windows' console layer. On Linux the terminal is asked
    # (TerminalInput.appearance) and the answer passed in. The gutter is
    # transparent and needs nothing from here.
    if appearance is None:
        appearance = "dark"
        state = os.path.join(os.environ.get("LOCALAPPDATA", ""), "wezterm-appearance")
        try:
            with open(state) as f:
                value = f.read().strip()
            if value in ("light", "dark"):
                appearance = value
        except OSError:
            pass
    try:
        with open(PALETTE, encoding="utf-8") as f:
            ink = json.load(f)[appearance]["status"].lstrip("#")
        return tuple(int(ink[i:i + 2], 16) for i in (0, 2, 4))
    except (OSError, ValueError, KeyError, TypeError):
        # the status line is the one thing that wants a colour, and a
        # document is still worth reading without it
        return FALLBACK

def clipboard(text):
    """Put text on the terminal's clipboard, through OSC 52.

    Nothing at this end has a clipboard - the nas is headless - so the text
    is written out as an escape and wezterm puts it on the desktop's. The
    same way neovim does it over ssh; see nvim/lua/options.lua.
    """
    payload = base64.standard_b64encode(text.encode("utf-8")).decode()
    sys.stdout.write(f"{ESC}]52;c;{payload}\x07")
    sys.stdout.flush()


# How far short of the measure a line has to stop before it is taken to have
# ended a paragraph rather than simply run out of room. In points, so it
# holds at any page size: about a character and a half. Measured on a
# manuscript, a line that merely wrapped stopped 4.7 short and one that
# ended a paragraph 17.2, with a word broken across the line between them at
# 13.9 - which is why a broken word is spotted by its hyphen rather than by
# how short the line is.
PARAGRAPH = 10.0


def wordless(text):
    """Whether a stretch of text says nothing: blank, or nothing but the
    control characters a broken word's hyphen comes back as. `strip()` is
    not enough - it takes whitespace off and leaves \x02 standing."""
    return not any(ch.isprintable() and not ch.isspace() for ch in text)


def rows_of(rects):
    """Rectangles gathered into the rows they sit on, left to right.

    Two pieces of one line overlap vertically; the next line down does not,
    because there is leading between them. That is the whole test.
    """
    rows = []
    for rect in sorted(rects, key=lambda r: (-r[3], r[0])):
        left, bottom, right, top = rect
        for row in rows:
            if min(top, row[0][3]) > max(bottom, row[0][1]):
                row.append(rect)
                break
        else:
            rows.append([rect])
    return [sorted(row, key=lambda r: r[0]) for row in rows]


def reflow(lines):
    """Printed lines joined back into paragraphs.

    A pdf breaks a line wherever the measure ran out, and those breaks mean
    nothing away from the page. What it does not carry is where a paragraph
    ended - there is no blank line in it to find - so that is read off the
    page's own spacing: the lines of a paragraph sit a leading apart and a
    new paragraph sits further down. Measured on a manuscript, a line within
    a paragraph fell 14.2 to 15.2 below the one before it and a new
    paragraph 24.2: a gap wide enough to see from either side.

    Shortness would be the obvious test and is the wrong one. This prose is
    set ragged right, so a line ends wherever the next word did not fit and
    says nothing about whether the paragraph ended with it - measured, a
    line that merely wrapped stopped anywhere from 4.7 to 11.6 short while
    one that ended a paragraph stopped 17.2.

    Each line arrives as (text, the height it ended at, or None for the last
    one, which no break measured).
    """
    pieces = []
    for body, y in lines:
        # \ufffe stands where a hyphen fell at the end of a line, and the
        # line covered another row of the page for it. The hyphen is kept:
        # pdfium marks one the page inserted to break a word and one that
        # was written the same way, and nothing in the text or the geometry
        # tells them apart - so "publi-cations" comes back with a hyphen it
        # does not want, which is plain to see and easy to mend, rather than
        # "becausewhile" losing one it does, which is neither
        rows = 1 + body.count("\ufffe")
        piece = " ".join(body.replace("\ufffe", "-").split())
        if piece:
            pieces.append([piece, y, rows])
    if not pieces:
        return ""

    # how far apart the rows of one paragraph sit, taken from the middle of
    # what was seen so one wide gap cannot drag it
    # a line is measured at its top, so the next one sits as many leadings
    # below it as it covered rows - two, where a word was broken across it
    steps = []
    for (_, y, _), (_, above, rows) in zip(pieces[1:], pieces[:-1]):
        if y is not None and above is not None:
            steps.append((above - y) / rows)
    steps.sort()
    leading = steps[len(steps) // 2] if steps else 0.0

    paragraphs, current, last_y, last_rows = [], "", None, 1
    for piece, y, rows in pieces:
        if current and leading and last_y is not None and y is not None:
            if (last_y - y) / last_rows > leading * 1.35:
                paragraphs.append(current)
                current = ""
        current = current + " " + piece if current else piece
        if y is not None:
            last_y, last_rows = y, rows
    if current:
        paragraphs.append(current)
    return "\n\n".join(paragraphs)

def mark(canvas, box):
    """Show a rectangle as selected, by turning its ink inside out.

    Inverting rather than tinting: the page is greyscale and may be set on
    either ground, and this reads as selected on both without the viewer
    having to know which it is.
    """
    left, top, right, bottom = (int(round(v)) for v in box)
    left, top = max(0, left), max(0, top)
    right, bottom = min(canvas.width, right), min(canvas.height, bottom)
    if right <= left or bottom <= top:
        return
    region = canvas.crop((left, top, right, bottom))
    if region.mode in ("LA", "RGBA"):
        # the ink turns over; the alpha stays, so the gutter is still clear
        bands = region.split()
        region = Image.merge(region.mode,
                             tuple(ImageChops.invert(b) for b in bands[:-1]) + (bands[-1],))
    else:
        region = ImageChops.invert(region)
    canvas.paste(region, (left, top))


def frame_escape(canvas, cols, rows, quality=92):
    # One iTerm2 escape for the whole frame: one decode in the terminal,
    # one atomic paint. iTerm2 because it is the only image protocol this
    # wezterm renders at all (kitty is absent from the build).
    buf = io.BytesIO()
    # Two encoders, chosen by what the frame is. A frame that is all page
    # travels as jpeg - measured at ~1.4ms against png's ~6ms, and smaller
    # besides; at native resolution the text shows no difference the eye
    # can find. A frame with gutter in it travels as png, for the alpha:
    # the gutter is transparent, so the terminal's own ground shows
    # through instead of a painted guess at it. compress_level=1 keeps
    # png in motion-frame territory. A page with no colour in it travels
    # grayscale either way - a third of the pixels for the terminal to
    # decode, which is where most of a frame's time goes on this stack.
    if canvas.mode in ("RGBA", "LA"):
        canvas.save(buf, "PNG", compress_level=1)
    else:
        canvas.save(buf, "JPEG", quality=quality, subsampling=2)
    b64 = base64.standard_b64encode(buf.getvalue()).decode()
    return (
        f"{ESC}]1337;File=inline=1;size={buf.getbuffer().nbytes};"
        f"width={cols};height={rows};preserveAspectRatio=0:{b64}\x07"
    )

class Viewer:
    def __init__(self, path, slideshow=False):
        self.path = os.path.abspath(path)
        # Slideshow holds a page number where scrolling holds an offset:
        # there is no position between pages to be in, so self.scroll is
        # left at each page's top and self.page is the truth.
        self.slideshow = slideshow
        self.page = 0
        self.cell_w, self.cell_h = CELL_W, CELL_H
        self.cell_measured = False
        self.faded = theme()
        self.scroll = 0.0     # top of the viewport, in document points
        self.scale = None     # px per point; None until first fit
        self.lock = threading.Lock()  # pdfium is not thread-safe
        self.render_s = None  # the pixel scale frames are being drawn at
        self.mtime = 0
        self.doc = None
        self.cache = {}       # (page, scale) -> rendered PIL image
        self.texts = {}       # page -> its text, for selecting
        self.selection = None # ((page, index), (page, index)), in reading order
        self.anchor = None    # where the drag that is making it started
        self.notice = None    # a word for the status line, until the next move
        self.load()

    # -- document ----------------------------------------------------------

    def load(self):
        try:
            self.mtime = os.stat(self.path).st_mtime
            with open(self.path, "rb") as f:
                data = f.read()
        except OSError as e:
            raise SystemExit(f"viewer: cannot read {self.path}: {e}")
        from PIL import ImageChops
        with self.lock:  # the prefetcher must not be mid-render through this
            if self.doc is not None:
                self.doc.close()
            self.doc = pdfium.PdfDocument(data)  # from memory: the file stays free
            # quick thumbnails decide whether the whole document travels as
            # grayscale. Every page gets a look, not just the first: the one
            # colour plate in a text manuscript is exactly the page that
            # matters. The sweep stops at the first colour it finds, so a
            # colour document pays almost nothing; an all-text one pays a
            # few milliseconds a page, once per load.
            self.gray = True
            for i in range(len(self.doc)):
                thumb = self.doc[i].render(scale=0.15).to_pil()
                r, g, b = thumb.split()
                spread = max(
                    ImageChops.difference(r, g).getextrema()[1],
                    ImageChops.difference(g, b).getextrema()[1],
                )
                if spread >= 16:
                    self.gray = False
                    break
            self.cache = {}
            self.texts = {}        # the old document's, now closed with it
            self.selection = None  # and its indices mean nothing here
            self.sizes = [self.doc[i].get_size() for i in range(len(self.doc))]
            self.tops = []
            y = 0.0
            for _, h in self.sizes:
                self.tops.append(y)
                y += h + GAP
            self.doc_h = y - GAP

    def changed_on_disk(self):
        try:
            return os.stat(self.path).st_mtime != self.mtime
        except OSError:
            return False

    # -- geometry ----------------------------------------------------------

    def viewport(self):
        size = shutil.get_terminal_size()
        if self.slideshow:
            # no status line, so the page takes every row but the last:
            # the cursor has to rest somewhere after the image, and an
            # image reaching the final row scrolls the screen and loses
            # its own top row.
            rows = size.lines - 1
        else:
            # the page, then a blank line's breath, then the status line
            rows = size.lines - 2
        cols = size.columns
        return cols, rows, cols * self.cell_w, rows * self.cell_h

    def page_at(self, y):
        return max(0, min(len(self.tops), bisect.bisect_right(self.tops, y)) - 1)

    def current_page(self):
        return self.page if self.slideshow else self.page_at(self.scroll)

    def clamp(self):
        if self.slideshow:
            self.page = max(0, min(len(self.tops) - 1, self.page))
            self.scroll = self.tops[self.page]
            return
        _, _, _, vh = self.viewport()
        limit = max(0.0, self.doc_h - vh / self.scale)
        self.scroll = max(0.0, min(limit, self.scroll))

    def fit_page(self):
        if self.slideshow:
            return  # the fit is the mode; there is nothing to set
        _, _, vw, vh = self.viewport()
        w, h = self.sizes[self.page_at(self.scroll)]
        self.scale = min(vw / w, vh / h)
        self.clamp()

    def fit_width(self):
        if self.slideshow:
            return
        _, _, vw, _ = self.viewport()
        w, _ = self.sizes[self.page_at(self.scroll)]
        self.scale = vw / w
        self.clamp()

    def zoom(self, factor):
        if self.slideshow:
            return
        _, _, _, vh = self.viewport()
        centre = self.scroll + vh / self.scale / 2
        self.scale = max(0.05, min(20.0, self.scale * factor))
        self.scroll = centre - vh / self.scale / 2
        self.clamp()

    # -- selecting ---------------------------------------------------------

    def textpage(self, i):
        if i not in self.texts:
            with self.lock:  # pdfium is not thread-safe
                self.texts[i] = self.doc[i].get_textpage()
        return self.texts[i]

    def where(self, col, row):
        """The cell the mouse is over, as a page and a point on it.

        The point is in the page's own coordinates, which count up from its
        foot, since that is what pdfium's text is measured in. `scale` comes
        back with it because the tolerance for finding a character is a cell
        wide, and a cell is a different number of points in each mode.
        None when the cell is off the page.
        """
        if self.scale is None:
            return None
        _, _, vw, vh = self.viewport()
        px, py = (col + 0.5) * self.cell_w, (row + 0.5) * self.cell_h
        if self.slideshow:
            page = self.page
            w, h = self.sizes[page]
            scale = min(vw / w, vh / h)
            x = (px - (vw - w * scale) / 2) / scale
            down = (py - (vh - h * scale) / 2) / scale
        else:
            scale = self.scale
            y = self.scroll + py / scale
            page = self.page_at(y)
            w, h = self.sizes[page]
            x = (px - (vw - w * scale) / 2) / scale
            down = y - self.tops[page]
        # a point beyond the page is pulled back onto its edge rather than
        # thrown away: dragging out into the gutter, or past the last line,
        # should carry the selection to the edge of the text the way it does
        # anywhere else, not stop dead
        x = min(max(x, 0.0), w)
        down = min(max(down, 0.0), h)
        return page, x, h - down, scale

    def index_at(self, col, row):
        """(page, character) under the mouse, or None when the mouse is not
        over a page at all."""
        spot = self.where(col, row)
        if spot is None:
            return None
        page, x, y, scale = spot
        text = self.textpage(page)
        index = text.get_index(x, y, self.cell_w / scale, self.cell_h / scale)
        if index is None:
            # a press in the margin, or between two lines, still means the
            # text nearest it: a drag that starts a little wide of the
            # column should take hold of it rather than do nothing
            index = self.nearest(page, x, y)
        return None if index is None else (page, index)

    def nearest(self, page, x, y):
        """The character closest to a point on a page."""
        text = self.textpage(page)
        best, at = None, None
        for i in range(text.count_chars()):
            left, bottom, right, top = text.get_charbox(i)
            dx = max(left - x, 0.0, x - right)
            dy = max(bottom - y, 0.0, y - top)
            away = dx * dx + dy * dy
            if best is None or away < best:
                best, at = away, i
        return at

    def select_to(self, spot, anchor=None):
        """Set the selection between the anchor and here, in reading order."""
        if spot is None:
            return
        if anchor is not None:
            self.anchor = anchor
        if self.anchor is None:
            return
        a, b = self.anchor, spot
        self.selection = (a, b) if a <= b else (b, a)
        self.notice = None

    def selected_text(self):
        """What is selected, as paragraphs rather than as printed lines."""
        if not self.selection:
            return ""
        (first, start), (last, end) = self.selection
        lines = []
        for page in range(first, last + 1):
            text = self.textpage(page)
            at = start if page == first else 0
            to = end if page == last else text.count_chars() - 1
            if to >= at:
                lines.extend(self.printed_lines(page, at, to))
        return reflow(lines)

    def selected_rects(self, page):
        """The rectangles covering the selection on one page, in its own
        coordinates - what the highlight is drawn from. These are pdfium's
        own, one per run of text set the same way, which is right for
        drawing even though it is wrong for reading; `printed_lines` puts
        them back into lines for that.
        """
        if not self.selection:
            return []
        (first, start), (last, end) = self.selection
        if not first <= page <= last:
            return []
        text = self.textpage(page)
        at = start if page == first else 0
        to = end if page == last else text.count_chars() - 1
        if to < at:
            return []
        return [text.get_rect(i) for i in range(text.count_rects(at, to - at + 1))]

    def printed_lines(self, page, at, to):
        """The selection on one page as printed lines: what each says, and
        where on the page it sat.

        The line breaks are pdfium's own, which is what makes this exact: a
        break is a real character in the text. Where the line sits is taken
        from the characters themselves - the highest box on it - rather than
        from the break, because a selection that stops in the middle of a
        line has no break at its end to measure by, and that last line is
        exactly the one a paragraph break is most often missed before. Not
        the rectangles - one of those is a run
        of text set the same way rather than a line, and neighbouring ones
        overlap, so text taken from them comes back repeating itself. Not
        the characters' own boxes either: a comma sits far lower than a
        capital, so a line cannot be told from its neighbours that way.
        """
        text = self.textpage(page)
        marks = [(text.get_text_range(i, 1), text.get_charbox(i)) for i in range(at, to + 1)]
        heights = sorted(b[3] - b[1] for _, b in marks if b[3] - b[1] > 0)
        if not heights:
            return []
        # a character sitting this far below the line it is in is not on it:
        # that is how the page number is parted from the last line of text,
        # which pdfium hands over as one run when the line above it ended in
        # a word broken across the page. Generous enough that a comma, which
        # sits well below a capital, stays where it belongs.
        drop = heights[len(heights) // 2] * 1.5

        # `line` is where the line began, which the gaps are measured from;
        # `row` is the row being read, which a drop is measured against,
        # and the two differ once a broken word has carried on below
        lines, current, line, row, left, i = [], [], None, None, None, 0
        while i < len(marks):
            ch, box = marks[i]
            if ch in ("\r", "\n"):
                lines.append(("".join(current), line))
                current, line, row, left = [], None, None, None
                if ch == "\r" and i + 1 < len(marks) and marks[i + 1][0] == "\n":
                    i += 1  # the pair is one break
            else:
                high = box[3] if box[3] - box[1] > 0 else None
                if high is not None and row is not None and row - high > drop:
                    # the rest of a word broken across the line begins at
                    # the margin, under the line it broke from. Something
                    # starting away to the right is a different block - the
                    # page number, which pdfium hands over as part of the
                    # last line when that line ended in a broken word
                    carries = (current and current[-1] == "\ufffe"
                               and left is not None and box[0] <= left + drop)
                    if carries:
                        row, left = high, box[0]
                    else:
                        lines.append(("".join(current), line))
                        current, line, row, left = [], None, None, None
                if high is not None:
                    row = high if row is None else max(row, high)
                    line = high if line is None else max(line, high)
                    left = box[0] if left is None else min(left, box[0])
                current.append(ch)
            i += 1
        if current:
            lines.append(("".join(current), line))
        # the page number, which is a line of its own at the foot of the page
        # and no part of what was written
        if lines and lines[-1][0].strip().isdigit():
            lines.pop()
        return lines

    # -- drawing -----------------------------------------------------------

    def page_image(self, i, s):
        key = (i, round(s, 4))
        if key not in self.cache:
            if len(self.cache) > 8:
                self.cache.pop(next(iter(self.cache)))
            with self.lock:
                img = self.doc[i].render(scale=s).to_pil()
            if self.gray:
                # converted once here, so every frame after is pure
                # grayscale: a third of the pixels to encode and decode
                img = img.convert("L")
            self.cache[key] = img
        return self.cache[key]

    def start_prefetcher(self):
        # A page render costs pdfium real time - hundreds of milliseconds
        # for a scanned page. This renders the neighbours ahead of the
        # reader, so the boundary is already in the cache by the time the
        # scroll arrives.
        def run():
            while True:
                time.sleep(0.05)
                s = self.render_s
                if s is None:
                    continue
                cur = self.current_page()
                for j in (cur + 1, cur - 1):
                    if 0 <= j < len(self.sizes) and (j, round(s, 4)) not in self.cache:
                        try:
                            self.page_image(j, s)
                        except Exception:
                            pass  # a reload mid-render; the next pass is fine

        threading.Thread(target=run, daemon=True).start()

    def build_frame(self):
        # the viewport's pixels, assembled but not yet spoken for
        cols, rows, vw, vh = self.viewport()
        if self.slideshow:
            return self.build_slide(cols, rows, vw, vh)
        if self.scale is None:
            w, h = self.sizes[0]
            self.scale = min(vw / w, vh / h)
        # a measured cell means the canvas is already native resolution;
        # otherwise oversample for crispness, within the pixel budget
        if self.cell_measured:
            ov = 1.0
        else:
            ov = min(OVERSAMPLE, max(1.0, (MAX_CANVAS / (vw * vh)) ** 0.5))
        s = self.scale * ov
        self.render_s = s  # what the prefetcher should render ahead at
        cw, ch = int(vw * ov), int(vh * ov)
        top_pts = self.scroll
        bot_pts = self.scroll + ch / s
        i = self.page_at(top_pts)

        # fast path: one page fills the whole canvas - the ordinary state
        # of fit-width reading - and the frame is a plain crop of the
        # cached page, with no background to fill and nothing to compose.
        # A selection has to be drawn over the page, so it takes the long
        # way round instead; the fast path stays for the reading that is
        # not selecting, which is nearly all of it.
        img = self.page_image(i, s)
        iw, ih = img.size
        x = (cw - iw) // 2
        y = int(round((self.tops[i] - top_pts) * s))
        if (not self.selection and x <= 0 and y <= 0
                and -x + cw <= iw and -y + ch <= ih):
            return img.crop((-x, -y, -x + cw, -y + ch)), cols, rows, vh

        # The gutter and the gaps between pages are transparent, not
        # painted: the terminal composites them over its own background,
        # so they match it exactly, whatever the theme is at that moment.
        # A painted colour cannot be trusted to - wezterm draws image
        # pixels through its own gamma handling, and a near-black ground
        # painted here lands visibly darker than the same colour drawn
        # as cell background beside it.
        canvas = Image.new("LA" if self.gray else "RGBA", (cw, ch))

        while i < len(self.tops) and self.tops[i] < bot_pts:
            img = self.page_image(i, s)
            iw, ih = img.size
            x = (cw - iw) // 2
            y = int(round((self.tops[i] - top_pts) * s))
            src_x0 = max(0, -x)
            src_y0 = max(0, -y)
            src_y1 = min(ih, src_y0 + (ch - max(0, y)))
            if src_y1 > src_y0:  # empty when the viewport top sits in a gap
                src = img.crop((src_x0, src_y0, min(iw, src_x0 + cw), src_y1))
                canvas.paste(src, (max(0, x), max(0, y)))
            # the selection on this page, drawn where the page just went
            for left, bottom, right, top in self.selected_rects(i):
                _, h = self.sizes[i]
                mark(canvas, (x + left * s, y + (h - top) * s,
                              x + right * s, y + (h - bottom) * s))
            i += 1

        return canvas, cols, rows, vh

    def build_slide(self, cols, rows, vw, vh):
        # one page, scaled until it fits whole, centred on both axes. The
        # scale is recomputed every frame rather than kept: pages can differ
        # in size, and a resize must refit without being told.
        w, h = self.sizes[self.page]
        self.scale = min(vw / w, vh / h)
        if self.cell_measured:
            ov = 1.0
        else:
            ov = min(OVERSAMPLE, max(1.0, (MAX_CANVAS / (vw * vh)) ** 0.5))
        s = self.scale * ov
        self.render_s = s
        cw, ch = int(vw * ov), int(vh * ov)
        img = self.page_image(self.page, s)
        iw, ih = img.size
        # the margin around the page is transparent for the same reason the
        # gutter is: the terminal composites its own ground behind it
        canvas = Image.new("LA" if self.gray else "RGBA", (cw, ch))
        at_x, at_y = max(0, (cw - iw) // 2), max(0, (ch - ih) // 2)
        canvas.paste(img.crop((0, 0, min(iw, cw), min(ih, ch))), (at_x, at_y))
        for left, bottom, right, top in self.selected_rects(self.page):
            mark(canvas, (at_x + left * s, at_y + (h - top) * s,
                          at_x + right * s, at_y + (h - bottom) * s))
        return canvas, cols, rows, vh

    def frame_string(self, sharp=True):
        canvas, cols, rows, vh = self.build_frame()
        if self.slideshow:
            # the page alone. The cursor is left on the spare last row,
            # which is why the image stops short of it.
            return (
                f"{ESC}[?2026h{ESC}[2J{ESC}[H"
                + frame_escape(canvas, cols, rows, quality=92 if sharp else 85)
                + f"{ESC}[{rows + 1};1H{ESC}[?2026l"
            )
        # the name of the file and the page number, nothing else: faded ink
        # on whatever the terminal's ground already is
        centre = self.scroll + vh / self.scale / 2
        line = f" {os.path.basename(self.path)}  ·  {self.page_at(centre) + 1}/{len(self.doc)}"
        if self.notice:
            line += f"  ·  {self.notice}"
        r, g, b = self.faded
        # the whole frame as one write inside a synchronized update: clear,
        # page and status arrive together, so nothing tears and nothing
        # flickers between the clear and the paint
        return (
            f"{ESC}[?2026h{ESC}[2J{ESC}[H"
            + frame_escape(canvas, cols, rows, quality=92 if sharp else 85)
            + f"{ESC}[{rows + 2};1H{ESC}[38;2;{r};{g};{b}m{line[:cols]}{ESC}[0m{ESC}[K"
            + f"{ESC}[?2026l"
        )

    def render(self, sharp=True):
        sys.stdout.write(self.frame_string(sharp))
        sys.stdout.flush()

    def state_key(self):
        # everything a drawn frame depends on; a prediction is only good
        # while this has not moved underneath it
        return (round(self.scroll, 3), self.page, self.scale, self.mtime,
                shutil.get_terminal_size())

    # -- movement ----------------------------------------------------------

    def step(self, direction, n=1):
        # a line or two of the terminal per j or k, times any count - or a
        # whole page each, in slideshow, where there is no partial position
        if self.slideshow:
            self.page += direction * int(n)
            self.clamp()
            return
        self.scroll += direction * n * (LINE * self.cell_h / self.scale)
        self.clamp()

    def page_step(self, direction, n=1):
        if self.slideshow:
            self.step(direction, n)
            return
        cur = self.page_at(self.scroll)
        if direction > 0:
            target = min(cur + n, len(self.tops) - 1)
        elif self.scroll > self.tops[cur] + 1:
            target = max(cur - (n - 1), 0)  # partway down: its top counts
        else:
            target = max(cur - n, 0)
        self.scroll = self.tops[target]
        self.clamp()

    def goto_page(self, number):
        target = max(0, min(len(self.tops) - 1, number - 1))
        self.page = target
        self.scroll = self.tops[target]
        self.clamp()

# The console's own input records. Written out here rather than inside the
# class that reads them, because a class body cannot see the names in the
# class body around it: a structure nested there naming another one raises
# NameError as the file is read, on Windows and nowhere else.
class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_int16), ("Y", ctypes.c_int16)]


class KEY_EVENT(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", ctypes.c_int32),
        ("wRepeatCount", ctypes.c_uint16),
        ("wVirtualKeyCode", ctypes.c_uint16),
        ("wVirtualScanCode", ctypes.c_uint16),
        ("UnicodeChar", ctypes.c_wchar),
        ("dwControlKeyState", ctypes.c_uint32),
    ]


class MOUSE_EVENT(ctypes.Structure):
    _fields_ = [
        ("dwMousePosition", COORD),
        ("dwButtonState", ctypes.c_uint32),
        ("dwControlKeyState", ctypes.c_uint32),
        ("dwEventFlags", ctypes.c_uint32),
    ]


class EVENT(ctypes.Union):
    _fields_ = [("KeyEvent", KEY_EVENT), ("MouseEvent", MOUSE_EVENT)]


class INPUT_RECORD(ctypes.Structure):
    _fields_ = [("EventType", ctypes.c_uint16), ("Event", EVENT)]


class ConsoleInput:
    # msvcrt throws away KEY_EVENT_RECORD.wRepeatCount: while a frame is
    # drawing, Windows coalesces queued key repeats into one record with a
    # count, and reading only the character loses the rest. Measured, that
    # was 12 of every 31 generated repeats surviving - scrolling felt like
    # 12Hz because most of it was quietly discarded. Reading the input
    # records directly keeps every step the keyboard actually made.

    def __init__(self):
        self.pointer = []
        self.k32 = ctypes.windll.kernel32
        self.handle = self.k32.GetStdHandle(-10)
        # The console reports the mouse only when asked, and only once
        # quick edit is off - quick edit takes a drag for itself and
        # makes a selection of its own out of it. Clearing it needs the
        # extended flag set in the same call. Untested on windows; the
        # linux half is what this was built against.
        self.mode = ctypes.c_uint32()
        if self.k32.GetConsoleMode(self.handle, ctypes.byref(self.mode)):
            ENABLE_MOUSE_INPUT, ENABLE_EXTENDED_FLAGS = 0x0010, 0x0080
            ENABLE_QUICK_EDIT_MODE = 0x0040
            wanted = (self.mode.value | ENABLE_MOUSE_INPUT | ENABLE_EXTENDED_FLAGS)
            self.k32.SetConsoleMode(self.handle, wanted & ~ENABLE_QUICK_EDIT_MODE)

    def read(self):
        # every pending (char, repeat_count) keydown; [] when nothing waits
        n = ctypes.c_uint32(0)
        if not self.k32.GetNumberOfConsoleInputEvents(self.handle, ctypes.byref(n)) or n.value == 0:
            return []
        records = (INPUT_RECORD * n.value)()
        got = ctypes.c_uint32(0)
        if not self.k32.ReadConsoleInputW(self.handle, records, n.value, ctypes.byref(got)):
            return []
        events = []
        for rec in records[: got.value]:
            if rec.EventType == 1 and rec.Event.KeyEvent.UnicodeChar != "\x00":
                # key-ups travel too: a release is a fact worth knowing
                events.append((
                    rec.Event.KeyEvent.UnicodeChar,
                    max(1, rec.Event.KeyEvent.wRepeatCount),
                    bool(rec.Event.KeyEvent.bKeyDown),
                ))
            elif rec.EventType == 2:  # MOUSE_EVENT
                self.pointer.append(self.pointer_from(rec.Event.MouseEvent))
        return [e for e in events]

    @staticmethod
    def pointer_from(ev):
        """One console mouse record, in the shape the linux half sends.

        dwEventFlags says what happened: 0 a button changed, 1 the
        mouse moved, 4 the wheel turned, and the wheel's direction is
        the sign of the high word of the button state.
        """
        col, row = ev.dwMousePosition.X, ev.dwMousePosition.Y
        MOUSE_MOVED, MOUSE_WHEELED = 0x0001, 0x0004
        if ev.dwEventFlags & MOUSE_WHEELED:
            up = ctypes.c_int32(ev.dwButtonState).value > 0
            return ("wheel-up" if up else "wheel-down", col, row)
        held = ev.dwButtonState & 0x0001  # the left button
        if ev.dwEventFlags & MOUSE_MOVED:
            return ("drag" if held else "move", col, row)
        return ("press" if held else "release", col, row)

    def mouse(self):
        out, self.pointer = self.pointer, []
        return out

    def restore(self):
        if getattr(self, "mode", None) is not None:
            self.k32.SetConsoleMode(self.handle, self.mode.value)

class TerminalInput:
    # The Linux half of the keyboard: stdin taken out of line mode so keys
    # arrive as they are pressed, and read whenever bytes are waiting. A
    # terminal sends no key-up, so a release is never seen; the main loop
    # already treats a pause in the repeats as one, since Windows' console
    # loses releases too.

    def __init__(self):
        self.pointer = []   # mouse events, waiting to be asked for
        self.partial = ""   # an escape split across two reads
        self.fd = sys.stdin.fileno()
        self.old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)  # not raw: output keeps its newline handling
        attrs = termios.tcgetattr(self.fd)
        # Enter stays \r rather than turning into ctrl-j's \n, and ctrl-s
        # stops being flow control, which would freeze the frames
        attrs[0] &= ~(termios.ICRNL | termios.IXON)
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)

    def read(self):
        data = self.partial
        self.partial = ""
        while select.select([self.fd], [], [], 0)[0]:
            chunk = os.read(self.fd, 4096)
            if not chunk:
                break
            data += chunk.decode("utf-8", "ignore")
        if not data:
            return []
        # a mouse report can be cut in half by the end of a read, and half
        # of one typed into the document would be a mess; hold it back
        cut = data.rfind("\x1b[<")
        if cut != -1 and not MOUSE.match(data, cut):
            self.partial, data = data[cut:], data[:cut]
        events, at = [], 0
        for m in MOUSE.finditer(data):
            events.extend((ch, 1, True) for ch in data[at:m.start()])
            self.pointer.append(pointer_event(m))
            at = m.end()
        events.extend((ch, 1, True) for ch in data[at:])
        return events

    def mouse(self):
        out, self.pointer = self.pointer, []
        return out

    def query(self, request, pattern, timeout=0.25):
        # a question for the terminal, and its answer if one comes in time
        sys.stdout.write(request)
        sys.stdout.flush()
        reply = ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            m = re.search(pattern, reply)
            if m:
                return m
            wait = max(0.0, deadline - time.monotonic())
            if select.select([self.fd], [], [], wait)[0]:
                reply += os.read(self.fd, 4096).decode("utf-8", "ignore")
        return None

    def appearance(self):
        # OSC 11 asks for the background colour; anything bright is light.
        # The reply is rgb:RRRR/GGGG/BBBB, so the top byte of each is enough.
        m = self.query(f"{ESC}]11;?{ESC}\\", r"\x1b\]11;rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)")
        if not m:
            return "dark"
        r, g, b = (int(c[:2], 16) for c in m.groups())
        return "light" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 128 else "dark"

    def restore(self):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

def pointer_event(m):
    """One mouse report as (what, column, row), counted from zero."""
    button, col, row, final = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
    col, row = col - 1, row - 1          # the terminal counts from one
    if button & 64:                      # the wheel, which is not a button
        return ("wheel-up" if button & 1 == 0 else "wheel-down", col, row)
    if final == "m":
        return ("release", col, row)
    return ("drag" if button & 32 else "press", col, row)


def measure_cell(con):
    # Ask the terminal for its cell size in pixels (XTWINOPS 16t), so pages
    # keep their true aspect whatever the font settings are. On Windows, VT
    # input is switched on only long enough to hear the answer, then
    # restored; on Linux the keyboard reader asks. When no answer comes,
    # the estimate measured against this repo's wezterm font stands in.
    if os.name != "nt":
        m = con.query(f"{ESC}[16t", r"\x1b\[6;(\d+);(\d+)t")
        if m and int(m.group(1)) > 0 and int(m.group(2)) > 0:
            return int(m.group(2)), int(m.group(1)), True
        return CELL_W, CELL_H, False
    k32 = ctypes.windll.kernel32
    handle = k32.GetStdHandle(-10)
    old = ctypes.c_uint32()
    if not k32.GetConsoleMode(handle, ctypes.byref(old)):
        return CELL_W, CELL_H, False
    try:
        k32.SetConsoleMode(handle, old.value | 0x0200)
        sys.stdout.write(f"{ESC}[16t")
        sys.stdout.flush()
        reply = ""
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline and not reply.endswith("t"):
            if msvcrt.kbhit():
                reply += msvcrt.getwch()
            else:
                time.sleep(0.01)
        m = re.search(r"\x1b\[6;(\d+);(\d+)t", reply)
        if m and int(m.group(1)) > 0 and int(m.group(2)) > 0:
            return int(m.group(2)), int(m.group(1)), True
    finally:
        k32.SetConsoleMode(handle, old.value)
    return CELL_W, CELL_H, False

def main():
    args = sys.argv[1:]
    slideshow = "-s" in args
    args = [a for a in args if a != "-s"]
    if len(args) != 1:
        raise SystemExit(1)  # the keys are in the docstring above, not on screen

    viewer = Viewer(args[0], slideshow=slideshow)
    con = ConsoleInput() if os.name == "nt" else TerminalInput()
    if os.name != "nt":
        viewer.faded = theme(con.appearance())
    viewer.cell_w, viewer.cell_h, viewer.cell_measured = measure_cell(con)
    # The primary screen, and the cursor left alone - both deliberately.
    # This stack shows images nowhere but the primary screen, and hiding
    # the cursor (ESC[?25l) silently suppresses every image drawn after
    # it: the costliest single fact in this file, established by bisecting
    # working frames against blank ones one escape at a time. The cursor
    # simply rests in the status line instead. Nothing here scrolls, so
    # the shell's history above survives untouched.
    sys.stdout.write(f"{ESC}[2J" + MOUSE_ON)
    count = ""      # digits gathering ahead of gg
    pending_g = False

    def handle(ch):
        # one key of the grammar; says whether the screen needs repainting
        nonlocal count, pending_g
        if pending_g:
            pending_g = False
            if ch == "g":
                viewer.goto_page(int(count) if count else 1)
                count = ""
                return "dirty"
            count = ""
        if ch.isdigit():
            count += ch
            return None
        if ch == "g":
            pending_g = True
            return None
        n = int(count) if count else 1
        count = ""
        if ch != "y":
            viewer.notice = None  # a word in the status line lasts until the next key
        if ch in ("q", "\x03"):
            return "quit"
        if ch == "j":
            viewer.step(1, n)
        elif ch == "k":
            viewer.step(-1, n)
        elif ch == "\n":      # ctrl-j
            viewer.page_step(1, n)
        elif ch == "\x0b":    # ctrl-k
            viewer.page_step(-1, n)
        elif ch == "G":
            viewer.goto_page(len(viewer.doc))
        elif ch == "z":
            viewer.zoom(1 / 1.25)  # out
        elif ch == "x":
            viewer.zoom(1.25)      # in
        elif ch == "Z":
            viewer.fit_page()
        elif ch == "X":
            viewer.fit_width()
        elif ch == "y":
            text = viewer.selected_text()
            if text:
                clipboard(text)
                viewer.notice = f"copied {len(text)} characters"
            else:
                viewer.notice = "nothing selected"
        elif ch == "\x1b":   # esc lets the selection go
            viewer.selection, viewer.anchor, viewer.notice = None, None, None
        elif ch == "r":
            viewer.load()
            viewer.clamp()
        else:
            return None
        return "dirty"

    try:
        viewer.render()
        viewer.start_prefetcher()
        last_size = shutil.get_terminal_size()
        last_check = time.monotonic()
        settle_at = None  # when a moving page owes itself a sharp frame
        predicted = None  # (state it was built from, scroll after, frame)
        quiet_since = time.monotonic()
        dirty = False     # a non-cruise action awaiting its immediate paint
        debt = 0.0        # bare j/k steps received but not yet painted
        debt_dir = 1
        next_frame = 0.0
        last_tick = 0.0
        last_scroll_key = 0.0
        TICK = 1 / 30     # two display frames at 60Hz: no beat judder
        RATE = 31.25      # steps/s a held key generates on stock Windows

        def stop(settle):
            # the cruise ends: whatever debt was buffering the clumps is
            # void, and a sharp frame is owed shortly
            nonlocal debt, last_tick, settle_at
            debt = 0.0
            last_tick = 0.0
            settle_at = time.monotonic() + settle
        while True:
            events = con.read()
            now = time.monotonic()
            for what, col, row in con.mouse():
                if what == "press":
                    viewer.anchor = None
                    viewer.selection = None
                    viewer.notice = None
                    viewer.select_to(viewer.index_at(col, row),
                                     anchor=viewer.index_at(col, row))
                    dirty = True
                elif what == "drag":
                    viewer.select_to(viewer.index_at(col, row))
                    dirty = True
                elif what in ("wheel-up", "wheel-down"):
                    # the wheel is the terminal's no longer, now that the
                    # mouse is being reported; it moves the page instead
                    viewer.step(-1 if what == "wheel-up" else 1, 3)
                    dirty = True
            if events:
                quiet_since = now
                # a lone tap of j with a prediction waiting: the frame is
                # already built and already sharp
                if (
                    predicted is not None
                    and debt == 0
                    and not dirty
                    and len(events) == 1
                    and events[0] == ("j", 1, True)
                    and not count
                    and not pending_g
                    and predicted[0] == viewer.state_key()
                ):
                    _, (viewer.scroll, viewer.page), frame = predicted
                    predicted = None
                    sys.stdout.write(frame)
                    sys.stdout.flush()
                    continue
                predicted = None
                quitting = False
                for ch, repeat, down in events:
                    if not down:
                        # a released scroll key stops the view instantly
                        if ch in ("j", "k") and debt and not viewer.slideshow:
                            stop(0.05)
                        continue
                    if (
                        ch in ("j", "k")
                        and not viewer.slideshow
                        and not count
                        and not pending_g
                    ):
                        # bare scrolling joins the cruise rather than
                        # painting per arrival
                        d = 1 if ch == "j" else -1
                        if debt and d != debt_dir:
                            debt = 0.0      # a direction flip drops the tail
                            last_tick = 0.0
                        debt_dir = d
                        debt += repeat
                        last_scroll_key = now
                        continue
                    for _ in range(repeat):
                        result = handle(ch)
                        if result == "quit":
                            quitting = True
                            break
                        dirty = dirty or result == "dirty"
                    if quitting:
                        break
                if quitting:
                    break

            # The cruise, as velocity: while steps are owed, the view moves
            # at the key-repeat rate, advanced by however much time truly
            # passed since the last frame, on a tick that divides the
            # display's own. The console layer delivers held-key repeats in
            # ragged clumps; buffering them as debt and spending them as
            # smooth motion is what makes scrolling read as movement
            # instead of lurches. Backlog is worked off as slightly higher
            # velocity, never as a visible double-step.
            if debt > 0:
                # no repeat for a while means the key is up even if the
                # release event never made it through the console layer
                if now - last_scroll_key > 0.08:
                    stop(0.05)
                    continue
                if now >= next_frame:
                    dt = (now - last_tick) if last_tick else TICK
                    last_tick = now
                    boost = 1.5 if debt > 6 else 1.0
                    move = min(debt, RATE * dt * boost)
                    viewer.step(debt_dir, move)
                    debt -= move
                    viewer.render(sharp=False)
                    next_frame = max(next_frame + TICK, time.monotonic())
                    if debt <= 0:
                        stop(0.12)
                else:
                    time.sleep(0.001)
                continue

            if dirty:
                viewer.render(sharp=False)
                dirty = False
                settle_at = time.monotonic() + 0.12
                continue

            if not events:
                if settle_at is not None and now >= settle_at:
                    settle_at = None
                    viewer.render(sharp=True)
                    continue
                # a reading pause: build the next j-step's sharp frame in
                # advance, so the next tap paints in the time of a write
                if predicted is None and settle_at is None and now - quiet_since > 0.2:
                    origin = viewer.state_key()
                    before = (viewer.scroll, viewer.page)
                    viewer.step(1)
                    if (viewer.scroll, viewer.page) != before:
                        frame = viewer.frame_string(sharp=True)
                        predicted = (origin, (viewer.scroll, viewer.page), frame)
                    viewer.scroll, viewer.page = before
                time.sleep(0.003)
                if now - last_check > 0.5:
                    last_check = now
                    if viewer.changed_on_disk():
                        viewer.load()
                        viewer.clamp()
                        predicted = None
                        viewer.render()
                    elif shutil.get_terminal_size() != last_size:
                        last_size = shutil.get_terminal_size()
                        predicted = None
                        viewer.render()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(MOUSE_OFF + f"{ESC}[2J{ESC}[H{ESC}[?25h")
        sys.stdout.flush()
        con.restore()

if __name__ == "__main__":
    main()
