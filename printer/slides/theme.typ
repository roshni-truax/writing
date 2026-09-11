// The look of a slide deck. slides.py prepends a `cfg` dictionary (theme,
// size, columns, font) taken from the deck's frontmatter, then this file,
// then the slides themselves as calls to the functions defined here.
//
// Everything sits on a character grid: the text block is exactly
// `cfg.columns` characters wide, so a line a plugin draws at that width
// reaches from margin to margin, and anything narrower lines up with the
// text above it.

// zenwritten's grounds and inks, arriving in `cfg` from slides.py, which
// reads them from palette/zenwritten.json - the file the editor's own theme
// is compiled into, so a deck is set in the colours it was written in.
// `faint` sits just off the ground: rules, an empty bar, slide numbers.
#let theme = cfg.palette

// A tone is one of the three the deck writes in, or `shade-N`: N percent of
// the way from the page's ground to its ink. That is how a plugin shades a
// field in more steps than three, and it comes out right either way round,
// since on a light page the ink is the dark end. The mixing is done in oklab
// so the steps look evenly spaced rather than merely being evenly numbered.
#let tone(name) = if name.starts-with("shade-") {
  let t = int(name.slice(6)) * 1%
  color.mix((theme.bg, 100% - t), (theme.fg, t), space: oklab)
} else {
  theme.at(name)
}

// JetBrains Mono's advance is 0.6em, so this is the width of one character.
// The gutter between a row's columns is counted in characters and arrives
// in `cfg` from slides.py, which splits the grid by the same number.
#let ch = 0.6 * cfg.size
#let text-width = cfg.columns * ch

// Something drawn in characters: a plugin's output or a fenced block. Each
// line is a list of (text, tone) pairs. Rows are set with no leading and
// the glyph box reaching ascender to descender, so box-drawing characters
// in one row meet those in the next.
//
// `scale` is 1 unless the fence said `small`, when slides.py sets the type
// smaller and hands the block proportionally more characters to fill the
// same width. Every measure here is taken from the block's own size, so a
// small block is the same drawing on a finer grid.
// The block takes the width of what it draws, not of the page. A column in
// a `::: row` is sized to its content, and a block claiming the full width
// would leave every column as wide as the room it was offered.
#let ascii(lines, scale: 1.0) = block(
  {
    let cell = 0.6 * scale * cfg.size
    set text(size: scale * cfg.size, top-edge: "ascender", bottom-edge: "descender")
    set par(leading: 0em)
    // Block elements (█ ▌ ▁ ░ and the rest of U+2580-259F) meet edge to
    // edge, and every renderer leaves a hairline where two shapes share a
    // pixel: each covers half of it, and half over half is not whole. So
    // each block glyph is drawn 5% larger, centered on its cell, over an
    // invisible copy that holds the cell's place on the grid. Neighbours
    // then overlap by a fraction of a point and the fill reads as one shape.
    show regex("[\u{2580}-\u{259F}]"): it => box(width: cell, {
      hide(it)
      place(top + left, dx: -0.025 * cell, dy: -0.033em, text(size: 1.05em, it.text))
    })
    lines.map(line =>
      line.map(seg => text(fill: tone(seg.at(1)), seg.at(0))).join()
    ).join(linebreak())
  },
)

// Powerpoint's width, at whatever aspect the frontmatter asks for (16:9
// unless it says otherwise). A pdf has no screen size: the viewer scales the
// page to fit, so a page in the screen's own aspect fills it edge to edge.
#let page-width = 254mm
#let page-height = page-width * cfg.aspect

// The footer is one line of the grid, set per slide by slides.py: the
// slide number, counted from `start`, at the right end of the progress bar
// when the deck has one. Slides outside start..end carry nothing.
#let footer-line = state("footer", none)

#set page(
  width: page-width,
  height: page-height,
  fill: theme.bg,
  margin: (x: (page-width - text-width) / 2, top: 1.6cm, bottom: 1.4cm),
  footer: context {
    let line = footer-line.get()
    if line != none { ascii((line,)) }
  },
)

// ExtraLight body and ExtraBold for bold, matching the pdf export and the
// terminal. Weight is the only thing that changes size never does: a title
// is body-sized and bold, a subtitle is body-sized and dim.
#set text(font: cfg.font, size: cfg.size, weight: 200, fill: theme.fg)
#show strong: set text(weight: 800)
#set par(leading: 0.65em, spacing: 1.3em)
// Lists step in two characters, like a quotation. A solid bullet, a ring, a
// triangle, a square, and then round again - the same four prose sets and
// the editor draws. The bullets are dim so the words come first.
#let bullets = ("•", "◦", "‣", "▪").map(m => text(fill: theme.dim, m))
#set list(marker: bullets, indent: 2 * ch, body-indent: ch)
#set enum(indent: 2 * ch, body-indent: ch)

// A slide is a page. Content sits at the top unless the `===` before the
// slide says center or bottom. `footer` is the footer line's segments, or
// none for the slide number alone.
//
// The body is measured first. Typst would otherwise let a slide that does
// not fit run on to a second page, which is a slide the author never wrote,
// carrying the same number and the same progress bar. Stopping instead
// makes it something to fix rather than something to notice later; slides.py
// turns the panic into a plain line.
#let room = page-height - 1.6cm - 1.4cm

#let slide(number: 0, align: "top", footer: none, ..parts) = {
  pagebreak(weak: true)
  footer-line.update(footer)
  let body = parts.pos().join()
  context {
    if measure(block(width: text-width, body)).height > room {
      panic("slide " + str(number) + " is taller than the page: shorten it, "
            + "split it at a ===, or set a block `small`")
    }
  }
  if align == "center" { v(1fr); body; v(1fr) }
  else if align == "bottom" { v(1fr); body }
  else { body }
}

// The slide's title: bold, nothing else.
#let title(t) = block(below: 1.3em, text(weight: 800, t))

#let subtitle(t) = par(text(fill: theme.dim, t))

// A quotation: the deck's own ink behind a dim hairline, the whole thing
// stepped in from the margin by two characters. The words are `fg` like any
// others (roshni, 2026-09-10) - the rule is what marks them as quoted, and
// prose sets one the same way.
#let quote(body) = pad(left: 2 * ch, block(
  width: 100%,
  inset: (left: 2 * ch),
  stroke: (left: 0.5pt + theme.dim),
  body,
))

// Empty rows, from blank lines left in the source beyond the first: each
// is one row of the grid, the height a line of characters takes.
#let air(n) = v(n * 1.32em)

// Blocks side by side, from a `::: row`. Each column arrives as its width
// in characters and its content; the widths are counted in `ch`, so the
// columns land on the same grid the characters do, and the gutter between
// them is the one slides.py split the grid by.
// `side` is where the row sits. The columns keep the widths they were given
// whatever it says, so the row is laid out once and then moved as one piece;
// sizing the columns to their contents instead would rearrange the row while
// claiming to center it, and squeeze a chart into wrapping.
//
// A row fills the grid, so there is nothing for `align` to do. What is moved
// is the difference between the grid and the ink: every column but the last
// is followed by another, so only the last one's unused tail is slack.
#let row(side: "left", ..cols) = {
  let items = cols.pos()
  let g = grid(
    columns: items.map(it => it.at(0) * ch),
    column-gutter: cfg.gutter * ch,
    align: top,
    ..items.map(it => it.at(1)),
  )
  if side == "left" { g } else {
    layout(room => {
      let last = items.last()
      let drawn = calc.min(measure(last.at(1)).width, last.at(0) * ch)
      let ink = items.slice(0, -1).map(it => (it.at(0) + cfg.gutter) * ch).sum(default: 0pt) + drawn
      let slack = calc.max(room.width - ink, 0pt)
      move(dx: if side == "center" { slack / 2 } else { slack }, g)
    })
  }
}

// Names above a block's columns, each turned a quarter turn, from a plugin
// that asked for them. `indent` is where the first column starts and `step`
// how wide one is, both in characters, so a name sits over its own column.
// Turned rather than flat because a column is a few characters wide and the
// names would otherwise run together; the row names opposite stay flat,
// since a row is one character tall and a name turned there has nowhere to
// go.
#let turned-names(indent, step, names, body) = {
  block(below: 0.5em, grid(
    columns: (indent * ch,) + names.map(_ => step * ch),
    align: bottom + center,
    [],
    ..names.map(n => rotate(-90deg, reflow: true, text(fill: theme.dim, n))),
  ))
  body
}

// An image fitted to the whole slide, from `size=full` on an image block.
// A slide is already a page, so "its own page" means filling this one; the
// image keeps its proportions inside the room the text would have had.
#let imagefull(path) = align(
  center + horizon,
  image(path, width: text-width, height: room, fit: "contain"),
)

// A rule across the grid, from `---` on a line of its own.
#let rule() = ascii((( ("─" * cfg.columns, "faint"), ),))

// Inline code, in the same face as everything else, so only the ink marks it.
#let code(t) = text(fill: theme.dim, t)
