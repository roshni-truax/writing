-- Neovim, set up for writing fiction rather than code.
--
-- A handful of plugins and nothing else: a statusline that has swallowed
-- the command line, markdown rendered in place, a file tree that slides in
-- from the left, a two-key jump to anywhere on screen, and git in a floating
-- window. The A5 pdf export is one pandoc call (lua/export.lua), and the
-- greyscale theme costs no plugin at runtime - it is compiled flat into
-- colors/zenwritten.lua, see lua/zenwritten_compile.lua. Everything else
-- here is plain vim settings.

vim.g.mapleader = " "
vim.g.maplocalleader = " "

require("options")

-- colour arrives before the plugins do: the compiled theme needs none of them
require("appearance")

-- lazy.nvim, bootstrapped on first run so this config works from a bare clone.
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.uv.fs_stat(lazypath) then
  vim.fn.system({
    "git", "clone", "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git", "--branch=stable", lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

local function plugins()
  require("lazy").setup("plugins", {
    ui = { border = "single" },
    change_detection = { notify = false },
    performance = {
      rtp = {
        -- stock plugins with no place in a writing setup. netrw included:
        -- a directory argument opens the file tree instead, below.
        disabled_plugins = {
          "gzip", "matchit", "netrwPlugin", "rplugin",
          "tarPlugin", "tohtml", "tutor", "zipPlugin",
        },
      },
    },
  })
end

-- Nothing needs a plugin before the first paint. Every plugin is
-- lazy-loaded, so the ~40ms lazy.nvim spends organising happens one tick
-- later: a bare `nvim` paints, then the file tree arrives; `nvim file.md`
-- paints the text plain, then filetype detection - held back with it, since
-- it is what drags in treesitter's parse and the markdown renderer - runs
-- and the page colours in. The work is the same; it just no longer stands
-- between you and the page.
--
-- `nvim .`, or any directory argument, swaps the directory buffer for the
-- tree, rooted at the directory that was asked for. netrw is disabled
-- outright (disabled_plugins above), so nothing races to claim that buffer
-- first.
local argc = vim.fn.argc(-1)
local dir = argc == 1 and vim.fn.isdirectory(vim.fn.argv(0)) == 1
  and vim.fn.fnamemodify(vim.fn.argv(0), ":p")
if #vim.api.nvim_list_uis() == 0 then
  plugins() -- headless: plugin installs and the like
else
  if argc > 0 and not dir then
    -- detection still names each buffer's filetype; only the event is held
    -- back, and with it everything the event drags in
    vim.opt.eventignore:append("FileType")
  end
  vim.schedule(function()
    plugins()
    if dir then
      local dirbuf = vim.api.nvim_get_current_buf()
      vim.cmd.enew()
      pcall(vim.api.nvim_buf_delete, dirbuf, { force = true })
      require("neo-tree.command").execute({ dir = require("writing").root(dir) })
    elseif argc == 0 then
      -- nothing asked for a file, so put the tree up; piped stdin is left alone
      if vim.api.nvim_buf_get_name(0) == "" and vim.api.nvim_buf_line_count(0) <= 1 then
        require("neo-tree.command").execute({ dir = require("writing").root() })
      end
    else
      vim.opt.eventignore:remove("FileType")
      for _, buf in ipairs(vim.api.nvim_list_bufs()) do
        local ft = vim.bo[buf].filetype
        if vim.api.nvim_buf_is_loaded(buf) and ft ~= "" then
          vim.api.nvim_buf_call(buf, function()
            vim.cmd("doautocmd FileType " .. ft)
          end)
        end
      end
    end
  end)
end

require("keymaps")
require("proofread")
require("export")
require("references").setup()
