-- zenwritten: a monochrome theme, with a matched light and dark variant.
-- <leader>b flips between them; the theme follows vim.o.background on its
-- own, and lua/appearance.lua decides which one startup gets.
--
-- Neither plugin below loads at runtime. lush rebuilt the same colours from
-- source on every startup, at ~45ms a time, so the result is compiled flat
-- into colors/zenwritten.lua and lua/lualine/themes/zenwritten.lua instead,
-- which load in about two. The specs stay pinned so the source is always on
-- hand to recompile from - see lua/zenwritten_compile.lua, where the
-- theme's configuration now lives.
return {
  {
    "zenbones-theme/zenbones.nvim",
    lazy = true,
    dependencies = { "rktjmp/lush.nvim" },
  },
}
