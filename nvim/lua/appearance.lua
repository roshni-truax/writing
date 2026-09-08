-- Which background to start with, and the colorscheme applied.
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
