# syntax

everything the two kinds of document read beyond ordinary markdown, and what
each reads by default. prose is set by pandoc as an a5 page; a deck, one whose
frontmatter says `slides: true`, is set by `slides/` on a character grid.
`printer` reads both and picks by the frontmatter.

read out of `printer.py`, `frontmatter.py`, `references.py`, `header.typ`,
`meta.yaml`, `slides/slides.py`, `slides/theme.typ` and the two plugins,
chart and diagram. `slides/example.md` exercises everything the deck half
reads.

## the command

```
printer file.md              the pdf lands beside the source, same name
printer file.md -o out.pdf   somewhere else instead
```

## frontmatter

both kinds open the same way: a fenced block on the very first line of the
file, `key: value` a line at a time. a key with nothing after the colon takes
the indented lines under it, which is how the margins are given; nothing else
nests. a blank line is skipped, and so is a comment, `#` or `//`. a file that
does not open with a fence has no frontmatter and is all body.

    ```
    theme: dark
    slides: true
    ```

every switch is `true` or `false`, and nothing else.

```
slides: false         set it as a deck rather than a manuscript
theme:                the grounds and inks, from palette/zenwritten.json.
                      dark or light, and it means the same to both kinds.
                      prose defaults to light, a deck to dark
```

# prose

## frontmatter

`meta.yaml` beside printer.py holds these before a document says anything,
and a document setting one wins over it.

```
skip-numbering: 0     that many opening pages carry no number, and the
                      count starts after them, so with 1 the second page
                      is "1"
references:           the file the sources come from, relative to the
                      document. references.json beside it by default, and
                      nothing at all if there is no such file
papersize: a5         the page
fontsize: 10pt        the body size
linestretch: 1.15     the leading, matching the screen's
margin:               horizontal and vertical set both of their sides;
  horizontal: 1.6cm   top, bottom, left and right set one each. book
  top: 1.7cm          margins for a page this size, a little more below
  bottom: 2cm         so the page number has room
```

## air and breaks

```
a blank line          the ordinary paragraph break
each one after it     one line of air, the body's own leading, as
                      `#v(1.15em)`; markdown would collapse the run. a run
                      at either end of the file is dropped, and one inside
                      a fenced or indented code block is left as it is
---                   a scene break: a short faded stroke, centered, 14% of
                      the line, with 2.6em of air either side
two trailing spaces   markdown's own hard break
> a quotation         set at the size a footnote is, behind a dim hairline
                      at its left, with air either side. the words stay the
                      body's own ink, as they do on a slide; the rule runs
                      the whole way down, however many paragraphs it holds
- item                a list, drawn • ◦ ‣ ▪ and round again after the
                      fourth, the same four a deck sets and the editor
                      draws while you write it
```

## headings

```
#                     the book's title, at typst's default spacing
##                    a chapter: 1.6em of air under it before the text
### and deeper        typst's defaults, unchanged
```

## blocks

each takes nothing inside it: what it does is all on the opening line.

    ``` pagebreak
    ```                   start a new page here

    ``` image="map.png"
    ```                   the image, centered, at the width of the text
                          block

    ``` image="map.png" size=0.6
    ```                   six tenths of that width. a portrait image taller
                          than the text block wants a size, or a full
                          below, or it runs off the page

    ``` image="map.png" size=full
    ```                   alone on a page of its own, centered on it. the
                          page breaks are weak, so this makes no blank page
                          at either end of a manuscript

anything else fenced is left as it is, code included.

## notes and citations

`{{ }}` around anything makes a footnote: typst sets it at the foot of the
page the mark is on, under a short rule, in smaller type. a note whose first
word is a key in the references file is a citation instead, and is written
out in chicago's notes-and-bibliography form.

```
{{a remark of my own}}     a footnote in your own words, as markdown
{{marx1954}}               a citation, with no page
{{marx1954, 36}}           with a page. anything goes here: 36, 36-38,
                           "chap. 3"
{{marx1954, 36, but see}}  and after a second comma, your own words,
                           which follow the citation inside the note
\{{not a note}}             the braces themselves, written out
```

every note is the short form - author, short title, locator - and `Ibid.`
when it follows a citation of the same source, `Ibid., 92.` for a different
page and `Ibid.` on its own for the same one. the full details of a source
are set once, by the ```references block, rather than in its first note.
code is left alone.

a first word that is not a key makes an ordinary note, so a mistyped key
prints as prose rather than stopping: `{{marx1594, 36}}` becomes a footnote
reading "marx1594, 36".

```references
```

sets the sources cited above it, alphabetically by surname, each hanging
under its first line. it takes nothing inside it, and a document that has
cited nothing refuses it.

## sources

`references.json` beside the document, keyed by the key a citation writes.
`type` says which shape the note takes; the rest are that shape's fields.
`author`, `editor` and `translator` hold lists.

```
book                  author title volume edition translator place
                      publisher year
article               author title journal volume issue year pages doi
chapter               author title book editor pages place publisher year
                      an essay in a collection is this too
website               author title site date url
thesis                author title kind school year
report                author title place publisher year
```

a name is `Karl Marx` or `Marx, Karl`: the comma says the surname is already
first, which is how to write one whose last word is not the surname, like
`Beauvoir, Simone de`, and a name ending in a comma is a body rather than a
person - `Laboria Cuboniks,` - left whole and never turned around.
`short-title` sets what the notes use, since every note is the short form;
without it they use the whole title.

## what pandoc is told, whatever the document says

```
![alt](path)          an image on its own line stays an image: implicit
                      figures are off, so no "Figure 1:" and no printed
                      caption. the alt text survives as alt text
a code block          highlighted monochrome
the type              JetBrainsMono NFM at weight 200, tracking -0.01em,
                      bold at 800, paragraph spacing 1.7em. set in
                      header.typ, not from the document
```

# a deck

## frontmatter

```
slides: true          what makes it a deck at all
theme: dark           or light
progress: false       a bar in the footer beside the number, filled to the
                      current slide, with a one-character gap at each
                      section
aspect: 16:9          the page's shape, always `width:height`
size: 13pt            one type size for the whole deck
columns: 72           the text block is exactly this many characters wide,
                      and the margins follow from it
font: JetBrainsMono NFM
                      the family, whose 0.6em advance is what the grid is
                      built on
```

the values above are the defaults.

## slides

`===` on a line of its own, three or more, goes between slides; a deck may
open with one, for its first slide. words after it describe the slide that
follows, and combine in any order on the one line. content sits at the top
unless a word says otherwise.

```
=== center            content centered on the page
=== bottom            content at the foot of the page
=== start             the first slide the numbering counts, and the first
                      of its sections; nothing before it carries a number
=== section           a section begins here: a one-character break in the
                      progress bar
=== end               the first slide the bar no longer counts
```

## blocks

```
a blank line          the gap between blocks
each one after it     one row of the grid. blank lines at the start and end
                      of a slide, around the ===, are ignored
a line ending in \    breaks the line where it stands, without the gap
#                     the slide's title: bold, no rule under it, 1.3em of
                      air below. one per slide; a second is a subtitle
## and deeper         a dim subtitle at the body size. every level below #
                      is the same
---                   a faint rule right across the grid
> a quotation         behind a dim hairline, stepped in two characters;
                      the words in the deck's own ink. consecutive lines
                      join into one
- item                a list, stepped in two characters a level and drawn
* item                • ◦ ‣ ▪, round again after the fourth; the bullets are
+ item                dim. a line indented past the marker continues the
                      item
1. item               a numbered list. nested by indenting, either kind
1) item
| a | table |         a pipe table, drawn in characters, columns two spaces
                      apart
|:--:|--:|            a separator row aligns its columns, centered, right,
                      else left, and puts a faint rule under the header
![alt](path)          an image on its own line, at the full grid width
![alt](path){width=60%}
                      at another width
**bold**              weight 800
*emphasis* _emphasis_ italic. neither marker fires mid-word
`code`                the same face as everything else, set dim: only the
                      ink marks it
[label](url)          a link
```

## wrappers

these nest.

```
::: center            everything inside moves as one block. a paragraph's
…                     lines stay left-aligned to one another and the widest
:::                   sets the width; something drawn in characters moves
                      by whole columns, so it keeps the grid
::: right             the same, to the other side
::: left
::: row               what it holds sits side by side, the grid split with
                      two characters between the columns. a blank line at
                      the wrapper's own depth starts the next column
::: row 2 1           numbers are the columns' shares, so the first is
                      twice the width of the second. one per column, or
                      none at all
::: row center        moves the whole row over as one piece: the columns
                      keep their widths, and what moves is the room the
                      last one did not use. right too. a row fills the
                      grid, so wrapping one in ::: center does nothing
::: left inside a row keeps several blocks together in one column instead
                      of each starting a new one
```

## fenced blocks

three or more backticks, or tildes. a language naming a file in `plugins/`
hands the body to it: bare words after it are the plugin's arguments,
`key=value` its options. the two below say how the block is set, whatever
drew it, and combine in any order with whatever the plugin reads.

```
small                 0.8 of the type size, on a grid with 0.8⁻¹ as many
                      characters, so a dense drawing fills the same width
                      more finely
title="parts done"    a dim line under the block, centered on what it drew
                      rather than on the grid, with a blank row between
```

a block naming an image sets one instead, the same way prose does, and takes
nothing inside it.

    ``` image="ridge.png"             the whole width of the grid
    ``` image="ridge.png" size=0.6    six tenths of it
    ``` image="ridge.png" size=full   fitted to the whole slide

a fence with no plugin language and no image is drawn verbatim, in
characters.

## what a plugin draws in

```
fg                    the ink the deck is written in
dim                   a step back: subtitles, labels, figures
faint                 just off the ground: rules, an empty bar, slide
                      numbers
shade-0 … shade-100   that percent of the way from the page's ground to its
                      ink, mixed in oklab so the steps look evenly spaced
                      and invert correctly on a light page. how a field
                      gets more steps than three
```

## the data a plugin reads

spacing is for the writer; nothing has to line up.

```
fiction 42            a label, and its numbers taken from the end of the
                      line
part one 41200 40000  unquoted, as many numbers are taken as every row can
                      spare and as leave the labels distinct, so this reads
                      as two while `part 3 44100` keeps its label and reads
                      as one
"part 1" 41200 40000  quoting settles it outright, and is how to say which
                      a line is
42  4.2  -7           plain numbers
60%                   a percentage, read as 0.6 and printed back as 60%
3/5                   a fraction, read as 0.6
1,200                 commas are ignored
// a note             a comment line, skipped; inside a plugin's block only
```

every figure prints back the way it was written: 50.0 stays 50.0, not 50.
only a number the code worked out itself, such as a padded axis bound, is
formatted.

## chart

the kind is the first bare word, `bar` if there is none.

```
bar                   a bar to the right of each label, figure after it.
                      the same as `bar horizontal`
bar vertical          the same rows as upright columns, labels beneath,
                      figures above, one space between columns
line                  one series of numbers per line, comma or space
                      separated, in braille dots. up to three, each a step
                      dimmer; an earlier series is never painted over
scatter               `x y` on each line, as braille dots
spark                 one series per line as a single row of ▁▂▃▄▅▆▇█
heatmap               a grid of values, each cell shaded by how large it
                      is. the first line names the columns, separated by
                      spaces; every line after it is a row's name and one
                      number per column. cells are solid blocks, each mixed
                      its own share of the way from the page to the ink, so
                      the scale is continuous rather than binned. there is
                      no legend
```

two or three numbers on a row: on either bar kind the bars nest rather than
sit side by side, shortest in front, so each ink owns the stretch where its
bar is the shortest one covering it. tones fg, dim, faint in the order
written. against a target, `41200 40000` fills to the target and shows the
overshoot brighter. equal values are one bar.

```
height=8              rows, for bar vertical, line and scatter
width=                columns; the whole grid by default
max=                  the top of the scale; the largest value
min=                  the bottom, on line and scatter; the smallest value
values=true           the figures on a bar chart
axis=true             the axis and its labels on line and scatter
bar=                  the width of a column in `bar vertical`, in
                      characters; its widest label or figure, three at
                      least
size=1                for a heatmap, how many squares across and down a
                      cell is drawn. one square is two characters beside
                      one row, which is as near square as this grid comes,
                      so size=3 is nine
names=turned          for a heatmap, column names turned a quarter turn
                      above the grid; flat writes them across the top, cut
                      to the column width. row names stay flat at the left
                      either way
```

## diagram

coordinates are only relative: the grid sizes itself so neighbours have
room, keeping the proportions the coordinates give. arrows leave and arrive
one cell clear of the text, are routed around anything in the way, and turn
as little as they can; two meeting in a cell merge into a junction.

```
(0,1) manuscript      the words, centered on that point
(0,1) -> (1,1)        an arrow between the text at two points
(0,1) <-> (1,1)       a head at both ends
(0,1) <- (1,1)        a head at the first end
(0,1) - (1,1)         a plain line, no head. a point with no text at it can
                      still be an end, and the line runs to the point
y=up                  y runs upward, as in tikz; down flips it
```
