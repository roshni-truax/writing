-- Which background to start with, and the colorscheme applied.
--
-- Colour is 24-bit, said outright rather than left to be worked out. The
-- compiled theme carries rgb and nothing else - `Normal` is `fg = 12303291`,
-- with no cterm colour anywhere in it - so without this there is no colour
-- at all, just undifferentiated text. Neovim turns it on by itself when it
-- can tell the terminal is up to it, and over ssh to the nas it cannot:
-- $COLORTERM is not forwarded, and the answer to its own query arrives too
-- late for a config that has already drawn. Every terminal this is opened
-- in is wezterm, so there is nothing to detect.
vim.o.termguicolors = true
--
-- On startup 'background' is taken from the terminal, so opening the editor
-- in a light window gives a light editor, alt+b included.
--
-- Neovim would normally work this out for itself by asking the terminal for
-- its background colour, but that query (OSC 11) never survives Windows'
-- console layer: a bare `nvim -u NONE` in a genuinely light WezTerm window
-- still comes up dark. So WezTerm writes its appearance to a file whenever
-- it changes and this reads it - see wezterm/wezterm.lua.
--
-- On Linux (the nas, over ssh) the query works and neovim answers it for
-- itself, so there is no file to read and this is skipped.
local file = vim.env.LOCALAPPDATA and io.open(vim.env.LOCALAPPDATA .. "/wezterm-appearance", "r")
if file then
  local value = vim.trim(file:read("l") or "")
  file:close()
  if value == "light" or value == "dark" then
    vim.o.background = value
  end
end

-- lualine re-reads its theme on ColorScheme; dropping the cached copy lets
-- a <leader>b flip reach the statusline's colours too
vim.api.nvim_create_autocmd("ColorScheme", {
  callback = function()
    package.loaded["lualine.themes.zenwritten"] = nil
  end,
})

vim.cmd.colorscheme("zenwritten")
