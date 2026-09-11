// Injected into every pdf export by printer.py beside this file. All the
// type lives here: pandoc has no variables for weight, tracking, or bold's
// exact face.
//
// printer.py includes the theme's four colours - bg, fg, dim, faint - just
// ahead of this, out of palette/zenwritten.json, so a manuscript is set in
// the same grounds and inks as a deck and as the editor it was written in.
#set page(fill: bg)
#set text(fill: fg)

// The body: the terminal's family, at ExtraLight rather than the screen's
// Regular (the 200 faces are installed for print only; the terminal doesn't
// use them), with the letters pulled a touch closer together.
#set text(
  font: "JetBrainsMono NFM",
  weight: 200,
  tracking: -0.01em,
)

// Bold on screen is drawn ExtraBold (800) by wezterm; match it in print. The
// weight is absolute on purpose: typst's default bold is relative (+300), and
// from this body it would land at 500.
#show strong: set text(weight: 800)

// Code spans and blocks in the same family as the body.
#show raw: set text(font: "JetBrainsMono NFM")

// Air between paragraphs: typst's default is 1.2em, which reads as barely
// more than a line break at this leading.
#set par(spacing: 1.7em)

// The page number, faded and tucked into the lower right. Set here rather
// than fighting the template: conf only touches paper, margin, numbering and
// columns, so an explicit footer survives it.
//
// Every page is numbered unless the document says otherwise. To hold the
// numbering back - for a title page, or a map on its own page - put this at
// the top of the manuscript:
//
//     ```{=typst}
//     #skip-numbering(1)
//     ```
//
// That many opening pages then carry no number, and the count starts after
// them, so with 1 the second page is "1" rather than "2".
#let front-pages = state("front-pages", 0)
#let skip-numbering(n) = front-pages.update(n)

#set page(footer: context {
  let page-number = counter(page).get().first()
  let skipped = front-pages.get()
  if page-number > skipped {
    align(right, text(size: 8pt, fill: dim, str(page-number - skipped)))
  }
})

// An image, centered on the text block, from
//
//     ``` image="ridge.png" size=0.6
//     ```
//
// which printer.py turns into a call to one of these two. `imageblock` sets
// it in the run of the text at that share of the text block's width;
// `imagepage`, which is what `size=full` means, gives it a page of its own.
// A portrait image taller than the text block wants a size, or it will run
// off the page. The page breaks are weak, so a full one makes no blank page
// at the start or end of a manuscript.
#let imageblock(path, width) = block(
  width: 100%,
  above: 1.7em,
  below: 1.7em,
  align(center, image(path, width: width)),
)

#let imagepage(path, width: 100%) = {
  pagebreak(weak: true)
  v(1fr)
  align(center, image(path, width: width))
  v(1fr)
  pagebreak(weak: true)
}

// The bullets, four deep and then round again: a solid bullet, a ring, a
// triangle, a square. Typst's own cycle is •, ‣, – , which is three shapes
// with no order to them; this is the same set the deck sets and the same
// the editor draws while the list is being written, so a list looks like
// itself wherever it is being looked at. Typst cycles the list, so the
// fifth level is a solid bullet again.
#set list(marker: ("•", "◦", "‣", "▪"))

// A block quotation (`>` in markdown, emitted as `#quote(block: true)`):
// set a little smaller, the size a footnote is, behind a hairline at its
// left. Typst's own is indented from both margins at the body size and
// carries no rule, which reads as a paragraph that has wandered inwards
// rather than as someone else speaking.
#let quote-size = 0.85em  // typst's own footnote size, so the two agree
#show quote.where(block: true): it => block(
  width: 100%,
  above: 1.7em,
  below: 1.7em,
  inset: (left: 1.2em),
  stroke: (left: 0.5pt + dim),
  text(size: quote-size, it.body),
)

// Scene breaks (`---` in markdown, emitted as `#divider()`): a short stroke
// in the middle of the line instead of the template's default, a rule
// across half the page, with extra air above and below so the scene change
// registers as a pause. This `let` shadows the template's own divider
// definition, so the body picks up this one.
#let divider() = block(
  width: 100%, // without this the block hugs the line and centering is a no-op
  above: 2.6em,
  below: 2.6em,
  align(center, line(
    length: 14%,
    stroke: (paint: dim, thickness: 0.5pt),
  )),
)

// And a clear pause after a chapter heading before the text begins. In the
// manuscripts a chapter is `##` (level 2); `#` is the book's title and keeps
// its default spacing.
#show heading.where(level: 2): set block(below: 1.6em)
