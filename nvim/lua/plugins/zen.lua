-- Writing mode: the file alone in a narrow column, on <leader>z.
--
-- Zen-mode opens the current buffer in a floating window 80 columns wide
-- and centred, which is the padding this is for; the file itself is
-- untouched, so wrapping, marks and undo all carry on as they were.
--
-- The statusline goes with it. `laststatus` is 3 here, one line for the
-- whole window, and zen-mode drops it to 0 while the mode is on, so there
-- is nothing under the text. The command line is already gone
-- (`cmdheight` 0), and noice puts it back for as long as a `:` command is
-- being typed, which is the only time it is wanted.
return {
  {
    "folke/zen-mode.nvim",
    cmd = "ZenMode",
    opts = {
      window = {
        width = 80,
        -- the ground stays the ground: the default dims everything
        -- outside the column, which on a greyscale theme reads as a
        -- smudge rather than a margin
        backdrop = 1,
      },
      -- the word count lualine keeps at the end of the statusline, put
      -- back in the corner while the statusline is gone (lua/zenwords.lua)
      on_open = function()
        require("zenwords").open()
      end,
      on_close = function()
        require("zenwords").close()
      end,
      plugins = {
        options = { laststatus = 0 },
        -- both of these want a program that is not here; asking for them
        -- on a machine without it is a message at every toggle
        tmux = { enabled = false },
        wezterm = { enabled = false },
      },
    },
  },
}
