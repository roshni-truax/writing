// The look of a slide deck. slides.py prepends a `cfg` dictionary (theme,
// size, columns, font) taken from the deck's frontmatter, then this file,
// then the slides themselves as calls to the functions defined here.
//
// Everything sits on a character grid: the text block is exactly
// `cfg.columns` characters wide, so a line a plugin draws at that width
// reaches from margin to margin, and anything narrower lines up with the
// text above it.

#let palettes = (
  // zenwritten's grounds and inks (see wezterm/zenwritten.lua). faint is
  // mixed to sit just off the ground: rules, empty bar, slide numbers.
  dark: (bg: rgb("#171213"), fg: rgb("#BBBBBB"), dim: rgb("#8E8E8E"), faint: rgb("#4E4849")),
  light: (bg: rgb("#EEEEEE"), fg: rgb("#353535"), dim: rgb("#5C5C5C"), faint: rgb("#B8B5B5")),
)
#let theme = palettes.at(cfg.theme)
#let tone(name) = theme.at(name)

// JetBrains Mono's advance is 0.6em, so this is the width of one character.
#let ch = 0.6 * cfg.size
#let text-width = cfg.columns * ch

// Something drawn in characters: a plugin's output or a fenced block. Each
// line is a list of (text, tone) pairs. Rows are set with no leading and
// the glyph box reaching ascender to descender, so box-drawing characters
// in one row meet those in the next.
#let ascii(lines) = block(
  width: 100%,
  {
    set text(top-edge: "ascender", bottom-edge: "descender")
    set par(leading: 0em)
    // Block elements (█ ▌ ▁ ░ and the rest of U+2580-259F) meet edge to
    // edge, and every renderer leaves a hairline where two shapes share a
    // pixel: each covers half of it, and half over half is not whole. So
    // each block glyph is drawn 5% larger, centred on its cell, over an
    // invisible copy that holds the cell's place on the grid. Neighbours
    // then overlap by a fraction of a point and the fill reads as one shape.
    show regex("[\u{2580}-\u{259F}]"): it => box(width: ch, {
      hide(it)
      place(top + left, dx: -0.025 * ch, dy: -0.033em, text(size: 1.05em, it.text))
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

// The footer is one line of the grid, set per slide: the progress bar when
// the deck has one, otherwise the slide number alone, faded, at the right.
// The first slide carries no number.
#let footer-line = state("footer", none)

#set page(
  width: page-width,
  height: page-height,
  fill: theme.bg,
  margin: (x: (page-width - text-width) / 2, top: 1.6cm, bottom: 1.4cm),
  footer: context {
    let line = footer-line.get()
    if line != none {
      ascii((line,))
    } else {
      let n = counter(page).get().first()
      if n > 1 {
        align(right, text(size: 0.7em, fill: theme.faint, str(n)))
      }
    }
  },
)

// ExtraLight body and ExtraBold for bold, matching the pdf export and the
// terminal. Weight is the only thing that changes size never does: a title
// is body-sized and bold, a subtitle is body-sized and dim.
#set text(font: cfg.font, size: cfg.size, weight: 200, fill: theme.fg)
#show strong: set text(weight: 800)
#set par(leading: 0.65em, spacing: 1.3em)
#set list(marker: text(fill: theme.dim, "-"), indent: 0pt, body-indent: ch)
#set enum(indent: 0pt, body-indent: ch)

// A slide is a page. Content sits at the top unless the `===` before the
// slide says centre or bottom. `footer` is the footer line's segments, or
// none for the slide number alone.
#let slide(align: "top", footer: none, ..parts) = {
  pagebreak(weak: true)
  footer-line.update(footer)
  let body = parts.pos().join()
  if align == "centre" { v(1fr); body; v(1fr) }
  else if align == "bottom" { v(1fr); body }
  else { body }
}

// The slide's title: bold, nothing else.
#let title(t) = block(below: 1.3em, text(weight: 800, t))

#let subtitle(t) = par(text(fill: theme.dim, t))

// A quotation: dim, behind a hairline, the whole thing stepped in from
// the margin by two characters.
#let quote(body) = pad(left: 2 * ch, block(
  width: 100%,
  inset: (left: 2 * ch),
  stroke: (left: 0.5pt + theme.dim),
  text(fill: theme.dim, body),
))

// A rule across the grid, from `---` on a line of its own.
#let rule() = ascii((( ("─" * cfg.columns, "faint"), ),))

// Inline code, in the same face as everything else, so only the ink marks it.
#let code(t) = text(fill: theme.dim, t)
