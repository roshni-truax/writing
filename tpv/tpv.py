"""tpv - a terminal pdf viewer.

Rolled here because nothing else runs on Windows: every existing terminal
pdf viewer leans on unix plumbing (pixel-size ioctls, shared memory) that
never grew a Windows half. This one doesn't. Pages are rasterised by
pdfium - the renderer inside Chrome, shipped as a prebuilt wheel - and
drawn with the iTerm2 inline-image escape, the one image protocol this
wezterm renders on Windows: one escape per frame, wrapped in a
synchronized update so every frame lands whole.

The document is one continuous scroll, the way a manuscript reads, not a
stack of screens. The pdf is read into memory and the file handle released
at once, so an export can overwrite the file while it is on screen; tpv
notices the change and quietly re-renders. That is the loop this exists
for: manuscript on the left, its pdf on the right, refreshing itself.

  tpv file.pdf

  j / k            a line or two down / up; counts work (5j)
  ctrl-j / ctrl-k  down / up a full page; counts work
  gg  XXgg  G      start / page XX / end
  z / x            zoom out / in
  Z / X            zoom until the whole page fits / its width fills
  r                reload the file
  q                quit
"""

import base64
import bisect
import ctypes
import io
import msvcrt
import os
import re
import shutil
import sys
import threading
import time

import pypdfium2 as pdfium
from PIL import Image

ESC = "\x1b"
# The terminal's cell, in px: measured against the repo's wezterm font
# (13pt JetBrains Mono at 1.15 line height). Off-estimates only stretch
# the page slightly; they never lose it.
CELL_W, CELL_H = 9, 20.3
OVERSAMPLE = 2          # render up to twice the guess; scaling down stays crisp
MAX_CANVAS = 4_000_000  # px budget per frame; the oversample yields to it
GAP = 12                # the breath between pages, in pdf points
LINE = 2                # rows of the terminal one j or k scrolls by

def theme():
    # The status line's faded ink, read the same way neovim reads the theme:
    # from the file wezterm writes its appearance to (see wezterm/wezterm.lua),
    # because the OSC query for the background never survives Windows'
    # console layer. The values are zenwritten's, mixed to sit on its exact
    # grounds. The gutter is transparent and needs nothing from here.
    appearance = "dark"
    state = os.path.join(os.environ.get("LOCALAPPDATA", ""), "wezterm-appearance")
    try:
        with open(state) as f:
            value = f.read().strip()
        if value in ("light", "dark"):
            appearance = value
    except OSError:
        pass
    if appearance == "light":
        return (150, 145, 146)
    return (110, 100, 102)

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

class Tpv:
    def __init__(self, path):
        self.path = os.path.abspath(path)
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
        self.load()

    # -- document ----------------------------------------------------------

    def load(self):
        try:
            self.mtime = os.stat(self.path).st_mtime
            with open(self.path, "rb") as f:
                data = f.read()
        except OSError as e:
            raise SystemExit(f"tpv: cannot read {self.path}: {e}")
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
        # the page, then a blank line's breath, then the status line
        cols, rows = size.columns, size.lines - 2
        return cols, rows, cols * self.cell_w, rows * self.cell_h

    def page_at(self, y):
        return max(0, min(len(self.tops), bisect.bisect_right(self.tops, y)) - 1)

    def clamp(self):
        _, _, _, vh = self.viewport()
        limit = max(0.0, self.doc_h - vh / self.scale)
        self.scroll = max(0.0, min(limit, self.scroll))

    def fit_page(self):
        _, _, vw, vh = self.viewport()
        w, h = self.sizes[self.page_at(self.scroll)]
        self.scale = min(vw / w, vh / h)
        self.clamp()

    def fit_width(self):
        _, _, vw, _ = self.viewport()
        w, _ = self.sizes[self.page_at(self.scroll)]
        self.scale = vw / w
        self.clamp()

    def zoom(self, factor):
        _, _, _, vh = self.viewport()
        centre = self.scroll + vh / self.scale / 2
        self.scale = max(0.05, min(20.0, self.scale * factor))
        self.scroll = centre - vh / self.scale / 2
        self.clamp()

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
                cur = self.page_at(self.scroll)
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
        # cached page, with no background to fill and nothing to compose
        img = self.page_image(i, s)
        iw, ih = img.size
        x = (cw - iw) // 2
        y = int(round((self.tops[i] - top_pts) * s))
        if x <= 0 and y <= 0 and -x + cw <= iw and -y + ch <= ih:
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
            i += 1

        return canvas, cols, rows, vh

    def frame_string(self, sharp=True):
        canvas, cols, rows, vh = self.build_frame()
        # the name of the file and the page number, nothing else: faded ink
        # on whatever the terminal's ground already is
        centre = self.scroll + vh / self.scale / 2
        line = f" {os.path.basename(self.path)}  ·  {self.page_at(centre) + 1}/{len(self.doc)}"
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
        return (round(self.scroll, 3), self.scale, self.mtime, shutil.get_terminal_size())

    # -- movement ----------------------------------------------------------

    def step(self, direction, n=1):
        # a line or two of the terminal per j or k, times any count
        self.scroll += direction * n * (LINE * self.cell_h / self.scale)
        self.clamp()

    def page_step(self, direction, n=1):
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
        self.scroll = self.tops[max(0, min(len(self.tops) - 1, number - 1))]
        self.clamp()

class ConsoleInput:
    # msvcrt throws away KEY_EVENT_RECORD.wRepeatCount: while a frame is
    # drawing, Windows coalesces queued key repeats into one record with a
    # count, and reading only the character loses the rest. Measured, that
    # was 12 of every 31 generated repeats surviving - scrolling felt like
    # 12Hz because most of it was quietly discarded. Reading the input
    # records directly keeps every step the keyboard actually made.

    class KEY_EVENT(ctypes.Structure):
        _fields_ = [
            ("bKeyDown", ctypes.c_int32),
            ("wRepeatCount", ctypes.c_uint16),
            ("wVirtualKeyCode", ctypes.c_uint16),
            ("wVirtualScanCode", ctypes.c_uint16),
            ("UnicodeChar", ctypes.c_wchar),
            ("dwControlKeyState", ctypes.c_uint32),
        ]

    class INPUT_RECORD(ctypes.Structure):
        pass

    def __init__(self):
        self.INPUT_RECORD._fields_ = [
            ("EventType", ctypes.c_uint16),
            ("KeyEvent", ConsoleInput.KEY_EVENT),
        ]
        self.k32 = ctypes.windll.kernel32
        self.handle = self.k32.GetStdHandle(-10)

    def read(self):
        # every pending (char, repeat_count) keydown; [] when nothing waits
        n = ctypes.c_uint32(0)
        if not self.k32.GetNumberOfConsoleInputEvents(self.handle, ctypes.byref(n)) or n.value == 0:
            return []
        records = (self.INPUT_RECORD * n.value)()
        got = ctypes.c_uint32(0)
        if not self.k32.ReadConsoleInputW(self.handle, records, n.value, ctypes.byref(got)):
            return []
        events = []
        for rec in records[: got.value]:
            if rec.EventType == 1 and rec.KeyEvent.UnicodeChar != "\x00":
                # key-ups travel too: a release is a fact worth knowing
                events.append((
                    rec.KeyEvent.UnicodeChar,
                    max(1, rec.KeyEvent.wRepeatCount),
                    bool(rec.KeyEvent.bKeyDown),
                ))
        return events

def measure_cell():
    # Ask the terminal for its cell size in pixels (XTWINOPS 16t), so pages
    # keep their true aspect whatever the font settings are. VT input is
    # switched on only long enough to hear the answer, then restored; when
    # no answer comes, the estimate measured against this repo's wezterm
    # font stands in.
    k32 = ctypes.windll.kernel32
    handle = k32.GetStdHandle(-10)
    old = ctypes.c_uint32()
    if not k32.GetConsoleMode(handle, ctypes.byref(old)):
        return CELL_W, CELL_H
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
    if len(args) != 1 or args[0] in ("-h", "--help"):
        print(__doc__)
        raise SystemExit(0 if args and args[0] in ("-h", "--help") else 1)

    tpv = Tpv(args[0])
    tpv.cell_w, tpv.cell_h, tpv.cell_measured = measure_cell()
    # The primary screen, and the cursor left alone - both deliberately.
    # This stack shows images nowhere but the primary screen, and hiding
    # the cursor (ESC[?25l) silently suppresses every image drawn after
    # it: the costliest single fact in this file, established by bisecting
    # working frames against blank ones one escape at a time. The cursor
    # simply rests in the status line instead. Nothing here scrolls, so
    # the shell's history above survives untouched.
    sys.stdout.write(f"{ESC}[2J")
    count = ""      # digits gathering ahead of gg
    pending_g = False

    def handle(ch):
        # one key of the grammar; says whether the screen needs repainting
        nonlocal count, pending_g
        if pending_g:
            pending_g = False
            if ch == "g":
                tpv.goto_page(int(count) if count else 1)
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
        if ch in ("q", "\x03"):
            return "quit"
        if ch == "j":
            tpv.step(1, n)
        elif ch == "k":
            tpv.step(-1, n)
        elif ch == "\n":      # ctrl-j
            tpv.page_step(1, n)
        elif ch == "\x0b":    # ctrl-k
            tpv.page_step(-1, n)
        elif ch == "G":
            tpv.goto_page(len(tpv.doc))
        elif ch == "z":
            tpv.zoom(1 / 1.25)  # out
        elif ch == "x":
            tpv.zoom(1.25)      # in
        elif ch == "Z":
            tpv.fit_page()
        elif ch == "X":
            tpv.fit_width()
        elif ch == "r":
            tpv.load()
            tpv.clamp()
        else:
            return None
        return "dirty"

    try:
        tpv.render()
        tpv.start_prefetcher()
        con = ConsoleInput()
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
                    and predicted[0] == tpv.state_key()
                ):
                    _, tpv.scroll, frame = predicted
                    predicted = None
                    sys.stdout.write(frame)
                    sys.stdout.flush()
                    continue
                predicted = None
                quitting = False
                for ch, repeat, down in events:
                    if not down:
                        # a released scroll key stops the view instantly
                        if ch in ("j", "k") and debt:
                            stop(0.05)
                        continue
                    if ch in ("j", "k") and not count and not pending_g:
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
                    tpv.step(debt_dir, move)
                    debt -= move
                    tpv.render(sharp=False)
                    next_frame = max(next_frame + TICK, time.monotonic())
                    if debt <= 0:
                        stop(0.12)
                else:
                    time.sleep(0.001)
                continue

            if dirty:
                tpv.render(sharp=False)
                dirty = False
                settle_at = time.monotonic() + 0.12
                continue

            if not events:
                if settle_at is not None and now >= settle_at:
                    settle_at = None
                    tpv.render(sharp=True)
                    continue
                # a reading pause: build the next j-step's sharp frame in
                # advance, so the next tap paints in the time of a write
                if predicted is None and settle_at is None and now - quiet_since > 0.2:
                    origin = tpv.state_key()
                    before = tpv.scroll
                    tpv.step(1)
                    if tpv.scroll != before:
                        frame = tpv.frame_string(sharp=True)
                        predicted = (origin, tpv.scroll, frame)
                    tpv.scroll = before
                time.sleep(0.003)
                if now - last_check > 0.5:
                    last_check = now
                    if tpv.changed_on_disk():
                        tpv.load()
                        tpv.clamp()
                        predicted = None
                        tpv.render()
                    elif shutil.get_terminal_size() != last_size:
                        last_size = shutil.get_terminal_size()
                        predicted = None
                        tpv.render()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(f"{ESC}[2J{ESC}[H{ESC}[?25h")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
