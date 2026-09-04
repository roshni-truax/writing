-- The statusline, and the command line folded into it.
--
-- cmdheight is 0, so the bottom line is gone entirely and the window is all
-- text. noice puts `:` commands and search back on that line only while you are
-- typing one, and routes messages to a small corner popup. What is left over -
-- a pending command, a macro being recorded - shows in the statusline itself.
return {
  {
    "folke/noice.nvim",
    event = "VeryLazy",
    dependencies = { "MunifTanjim/nui.nvim" },
    opts = {
      cmdline = { view = "cmdline" }, -- bottom line, and only while typing
      messages = { view = "mini", view_error = "mini", view_warn = "mini" },
      notify = { enabled = false },
      lsp = { progress = { enabled = false } },
      presets = { bottom_search = true, long_message_to_split = true },
    },
  },

  {
    "nvim-lualine/lualine.nvim",
    dependencies = { "nvim-tree/nvim-web-devicons", "folke/noice.nvim" },
    event = "VeryLazy",
    config = function()
      local noice = require("noice")

      -- Words, not bytes: the number that matters in a manuscript.
      local function words()
        local w = vim.fn.wordcount()
        return (w.visual_words or w.words or 0) .. " words"
      end

      require("lualine").setup({
        options = {
          theme = "zenwritten",
          globalstatus = true,
          section_separators = "",
          component_separators = "",
        },
        sections = {
          lualine_a = { { "mode", fmt = string.lower } },
          lualine_b = { { "filename", path = 0 } },
          lualine_c = {},
          lualine_x = {
            { noice.api.status.command.get, cond = noice.api.status.command.has },
            { noice.api.status.mode.get, cond = noice.api.status.mode.has },
          },
          lualine_y = { words },
          lualine_z = { "location" },
        },
        inactive_sections = {
          lualine_a = {},
          lualine_b = {},
          lualine_c = { "filename" },
          lualine_x = {},
          lualine_y = {},
          lualine_z = {},
        },
      })
    end,
  },
}
