---
slides: true
theme: dark
progress: true
---

=== centre

# an example deck

## everything slides reads, on nine pages

=== start

# where the draft stands

three of five parts are through revision. the fourth is in first draft
and the fifth is an outline with **two** scenes written.

| part   | words | state       |
|--------|------:|-------------|
| one    | 41200 | revised     |
| two    | 38900 | revised     |
| three  | 44100 | revised     |
| four   | 15300 | first draft |
| five   |  2100 | outline     |

===

# words per part

```chart bar
part one    41200 40000
part two    38900 40000
part three  44100 40000
part four   15300 40000
part five   2100 40000
```

two numbers a row: what is written, then the target. the shorter bar sits
in front, so the ink changes where the smaller number falls. part four's
brighter stretch is the words it has; part three's is the overshoot.

- the parts are meant to sit near *forty thousand*
- part three runs long; see `cut-list.md`
  - the harbour chapter can lose a scene
  - so can the letter

=== section

# pace, words a day over the last month

```chart line height=10
800 1200 950 300 0 0 1400 1600 1100 900 400 0 0 1300 1500 1700 1200 800 0 0 1100 1000 900 1300 1200 0 0 1500 1600 1400
```

> a working day is a thousand words; a good one is fifteen hundred.

```chart spark
800 1200 950 300 1400 1600 1100 900 1300 1500 1700 1200
```

===

# revision by month

```chart bar vertical small height=8
jan 12 9 4
feb 9 7 2
mar 14 11 6
apr 3 2 1
may 11 8 5
jun 8 6 3
```

three numbers here: chapters revised, sent, and signed off. `small` sets a
block in smaller type on a finer grid, for a chart too dense for the page.

=== 

# side by side, two shares to one

::: row 2 1
```chart bar left-title="words a part"
part one 41200
part two 38900
part three 44100
part four 15300
```

```chart bar vertical height=6 title="parts done"
done 3
left 2
```
:::

`::: row` splits the grid between its columns, a blank line starting each
one. `title=` goes under a block; `left-title=` stands at its left, turned.

=== section

# how a manuscript becomes a pdf

```diagram
(0,1) manuscript
(1,1) pandoc
(2,1) typst
(2,0) pdf
(0,0) tpv
(0,1) -> (1,1)
(1,1) -> (2,1)
(2,1) -> (2,0)
(2,0) -> (0,0)
(0,0) - (0,1)
```

text at points, arrows between them. the grid spaces itself, and each
arrow is routed around whatever text is in its way.

===

# a box, drawn by hand

```
┌──────────────────────────────┐
│  fenced blocks pass straight │
│  through, as drawn.          │
└──────────────────────────────┘
```

1. numbered lists work
2. and so do [links](https://truax.io)

a line that ends in a backslash \
breaks here, with no gap.



three blank lines above this: the first is the ordinary gap, the other
two are rows of air.

=== bottom

# the last counted slide

sits at the foot of the page.

::: centre
this paragraph and the chart under it are centred as blocks: the lines
of the paragraph stay left-aligned to one another, and the chart moves
by whole columns.

```chart bar vertical height=4
one 3
two 5
three 2
```
:::

=== end centre

# the end
