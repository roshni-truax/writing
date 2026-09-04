-- nvim-surround: add, change and delete the delimiters around text - quotes,
-- brackets, and here mostly markdown emphasis.
--
-- Any bare punctuation already works as a surround (ysiw* gives *word*,
-- ysiw` gives `word`), so italics and code need no configuration. Two
-- markdown surrounds are added on top:
--
--   e  emphasis: **bold**, since bold is two keystrokes of * otherwise
--   l  link: [text](url), prompting for the url
--
-- The visual-mode mapping is gs rather than the plugin's default S, which
-- leap already uses to jump backward from a selection. As of v4 that cannot
-- be configured through setup(): the default visual maps are switched off
-- with a g: flag (which must be set before the plugin loads, hence `init`),
-- and gs / gS bind to the <Plug> mappings instead.
return {
  {
    "kylechui/nvim-surround",
    event = "VeryLazy",
    init = function()
      vim.g.nvim_surround_no_visual_mappings = true
    end,
    config = function(_, opts)
      require("nvim-surround").setup(opts)
      vim.keymap.set("x", "gs", "<Plug>(nvim-surround-visual)", { desc = "surround selection" })
      vim.keymap.set("x", "gS", "<Plug>(nvim-surround-visual-line)", { desc = "surround selection, own lines" })
    end,
    opts = {
      surrounds = {
        ["e"] = {
          add = { "**", "**" },
          find = "%*%*.-%*%*",
          delete = "^(%*%*)().-(%*%*)()$",
        },
        ["l"] = {
          add = function()
            local url = require("nvim-surround.config").get_input("link url: ")
            if url then
              return { { "[" }, { "](" .. url .. ")" } }
            end
          end,
          find = "%b[]%b()",
          delete = "^(%[)().-(%]%b())()$",
          change = {
            target = "^()()%b[]%((.-)()%)$",
            replacement = function()
              local url = require("nvim-surround.config").get_input("link url: ")
              if url then
                return { { "" }, { url } }
              end
            end,
          },
        },
      },
    },
  },
}
