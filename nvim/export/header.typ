// Injected into every pdf export (see lua/export.lua). All the type lives
// here: pandoc has no variables for weight, tracking, or bold's exact face.

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
    align(right, text(size: 8pt, fill: luma(45%), str(page-number - skipped)))
  }
})

// An image alone on its own page, centred. In markdown:
//
//     ```{=typst}
//     #imagepage("ridge.png")
//     ```
//
// The image fills the width of the text block; pass another width to change
// it, e.g. `#imagepage("ridge.png", width: 60%)`. A portrait image taller
// than the text block needs one, or it will run off the page. The page breaks
// are weak, so this makes no blank page at the start or end of a manuscript.
#let imagepage(path, width: 100%) = {
  pagebreak(weak: true)
  v(1fr)
  align(center, image(path, width: width))
  v(1fr)
  pagebreak(weak: true)
}

// Scene breaks (`---` in markdown, emitted as `#divider()`): a short, faded
// stroke in the middle of the line instead of the template's default, a rule
// across half the page, with extra air above and below so the scene change
// registers as a pause. This `let` shadows the template's own divider
// definition, so the body picks up this one.
#let divider() = block(
  width: 100%, // without this the block hugs the line and centering is a no-op
  above: 2.6em,
  below: 2.6em,
  align(center, line(
    length: 14%,
    stroke: (paint: luma(45%), thickness: 0.5pt),
  )),
)

// And a clear pause after a chapter heading before the text begins. In the
// manuscripts a chapter is `##` (level 2); `#` is the book's title and keeps
// its default spacing.
#show heading.where(level: 2): set block(below: 1.6em)
