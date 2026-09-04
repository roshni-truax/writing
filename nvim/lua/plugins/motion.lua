-- leap: jump anywhere on screen by typing two characters of where you are
-- going. s forward, S backward, then the two characters; if several places
-- match, a label appears at each and one more key picks between them.
--
-- Deliberately colourless, like everything else here. Out of the box leap
-- paints its labels magenta and its matches cyan. Instead the backdrop dims to
-- Comment grey and the labels are inverse video - background and foreground
-- swapped - which is the strongest signal a monochrome screen has. Those
-- groups are part of the theme (lua/zenwritten_compile.lua).
-- The github repo is a tombstone: upstream moved to codeberg in early 2026 and
-- replaced main with a commit that deletes everything, which is why a github
-- install "works" but contains no code. Hence the explicit url.
return {
  {
    url = "https://codeberg.org/andyg/leap.nvim",
    name = "leap.nvim",
    keys = {
      { "s", "<Plug>(leap-forward)", mode = { "n", "x", "o" }, desc = "leap forward" },
      { "S", "<Plug>(leap-backward)", mode = { "n", "x", "o" }, desc = "leap backward" },
    },
    config = function()
      -- Registered explicitly: leap only auto-detects a LeapBackdrop group if
      -- it exists before its own init runs, which is a timing accident. This
      -- is the supported call behind that detection.
      require("leap.user").set_backdrop_highlight("LeapBackdrop")
    end,
  },
}
