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
  tracking: -0.03em,
)

// Bold on screen is drawn ExtraBold (800) by wezterm; match it in print. The
// weight is absolute on purpose: typst's default bold is relative (+300), and
// from this body it would land at 500.
#show strong: set text(weight: 800)

// Code spans and blocks in the same family as the body.
#show raw: set text(font: "JetBrainsMono NFM")

// How one paragraph is told from the next. printer.py sets `par-spacing`
// and `par-indent` just ahead of this, out of the document's `spacing`:
//
//   internet      a gap between paragraphs and no indent. 1.7em, since
//                 typst's own 1.2em reads as barely more than a line
//                 break at this leading
//   traditional   the first line indented and no gap: the spacing is the
//                 leading itself, so the column runs unbroken
//
// `all: false` is what leaves the first paragraph of a chapter, and the
// one after a scene break or an image, unindented, which is how a book
// sets them.
#set par(
  spacing: par-spacing,
  first-line-indent: (amount: par-indent, all: false),
)

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
//
// The rule is `faint` rather than `dim`: it marks where the quotation runs
// and has nothing to say on its own. The words stay the body's ink, and
// the deck's rule is still dim - roshni's call, prose only.
//
// Under traditional spacing there is no rule at all and a little less air
// either side: printer.py sets `quote-rule` to `none` and `quote-air`
// shorter. A column with no gaps between its paragraphs needs only the
// indent to say a quotation has started, and the rule beside it reads as a
// second announcement of the same thing.
#let quote-size = 0.85em  // typst's own footnote size, so the two agree
#show quote.where(block: true): it => block(
  width: 100%,
  above: quote-air,
  below: quote-air,
  inset: (left: 1.2em),
  stroke: if quote-rule == none { none } else { (left: 0.5pt + quote-rule) },
  text(size: quote-size, it.body),
)

// A labelled break (`--- the next morning ---` in markdown, emitted as
// `#labelled(..)`): a hairline the whole width of the text block with the
// words sitting in a gap in the middle of it, everything in dim. Where a
// plain `---` is a pause in the telling, this one says what comes next -
// a part title, a date, a change of place - so it takes the full measure
// rather than the short centred stroke, and keeps the same air either side.
#let labelled(label) = block(
  width: 100%,
  above: 2.6em,
  below: 2.6em,
  {
    let rule = box(width: 1fr, line(
      length: 100%,
      stroke: (paint: dim, thickness: 0.5pt),
    ))
    grid(
      columns: (1fr, auto, 1fr),
      align: horizon,
      rule,
      box(inset: (x: 0.9em), text(fill: dim, label)),
      rule,
    )
  },
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
