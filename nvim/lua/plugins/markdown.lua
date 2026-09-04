-- Markdown drawn in the buffer as you write it. Uses the markdown treesitter
-- parsers Neovim already ships with, so nothing is compiled.
--
-- Deliberately colourless. Out of the box this plugin links heading backgrounds
-- to the diff highlights - H1 to DiffText, H2 to DiffAdd, H4 to DiffDelete -
-- which paints green and red blocks across a manuscript.
--
-- Headings are left as plain text and styled through treesitter instead of
-- being redrawn by the plugin. The hashes stay where you typed them, and the
-- six levels separate by weight and brightness rather than by colour, icon or
-- indentation. That is the whole hierarchy a terminal can express: it has no
-- type sizes, so contrast has to do the work. The ramp itself is part of the
-- theme (lua/zenwritten_compile.lua), as are the plugin's few grey groups.
return {
  {
    "MeanderingProgrammer/render-markdown.nvim",
    ft = { "markdown" },
    opts = {
      render_modes = { "n", "v", "i", "c" }, -- stays rendered while typing
      sign = { enabled = false },

      -- The hashes are concealed and nothing is drawn in their place.
      --
      -- Two details matter and both are easy to get wrong. The icons must be
      -- empty *strings*, not an empty list: the renderer does
      -- `if not icon then return end` before it ever adds the conceal, so an
      -- empty list leaves the hashes on screen. And `backgrounds` must be empty
      -- so no background mark is created - one painted across the heading
      -- carries Normal's foreground with it and flattens the colour set below,
      -- which shows up as a heading that dims the moment the cursor leaves it.
      heading = {
        icons = { "", "", "", "", "", "" },
        backgrounds = {},
        position = "inline",
      },

      -- A faint slab, no language badge.
      code = {
        width = "block",
        left_pad = 2,
        right_pad = 2,
      },

      bullet = { icons = { "-", "-", "-", "-" } },
      quote = { icon = "|" },
      dash = { icon = "-" },
      checkbox = { enabled = false },
      link = { enabled = false }, -- link syntax is text, not chrome
    },
  },
}
