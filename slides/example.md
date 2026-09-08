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
part one    41200
part two    38900
part three  44100
part four   15300
part five   2100
```

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

===

# revision by month

```chart bar vertical height=8
jan 12
feb 9
mar 14
apr 3
may 11
jun 8
```

---

```chart spark
12 9 14 3 11 8 10 15 14 12
```

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
