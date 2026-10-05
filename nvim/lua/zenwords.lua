-- The word count in the corner of writing mode.
--
-- Writing mode takes the statusline away (`laststatus` 0), and with it the
-- count lualine keeps at the right-hand end. This puts it back as a small
-- floating window in the bottom right, in the theme's faint ink - there to
-- glance at, quiet enough to write past.
--
-- The count is what lualine shows, `wordcount()`, so the two never
-- disagree: the words in the file, or the words in the selection while
-- something is selected.

local M = {}

local win, buf
local group = vim.api.nvim_create_augroup("zenwords", { clear = true })

local function count()
  local w = vim.fn.wordcount()
  return " " .. (w.visual_words or w.words or 0) .. " words "
end

local function draw()
  if not win or not vim.api.nvim_win_is_valid(win) then
    return
  end
  local text = count()
  vim.bo[buf].modifiable = true
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, { text })
  vim.bo[buf].modifiable = false
  vim.api.nvim_win_set_config(win, {
    relative = "editor",
    anchor = "SE",
    row = vim.o.lines - 1,
    col = vim.o.columns,
    width = #text,
    height = 1,
  })
end

function M.open()
  if win and vim.api.nvim_win_is_valid(win) then
    return
  end
  buf = vim.api.nvim_create_buf(false, true)
  vim.bo[buf].bufhidden = "wipe"
  win = vim.api.nvim_open_win(buf, false, {
    relative = "editor",
    anchor = "SE",
    row = vim.o.lines - 1,
    col = vim.o.columns,
    width = 12,
    height = 1,
    style = "minimal",
    focusable = false,
    noautocmd = true,
    -- above the zen window and its backdrop, which sit at 40 and 50
    zindex = 100,
  })
  vim.wo[win].winhighlight = "NormalFloat:ZenWords,FloatBorder:ZenWords"
  vim.wo[win].winblend = 0
  draw()
  vim.api.nvim_create_autocmd(
    { "TextChanged", "TextChangedI", "CursorMoved", "CursorMovedI", "ModeChanged",
      "BufEnter", "VimResized", "WinResized" },
    { group = group, callback = draw }
  )
end

function M.close()
  vim.api.nvim_clear_autocmds({ group = group })
  if win and vim.api.nvim_win_is_valid(win) then
    vim.api.nvim_win_close(win, true)
  end
  win, buf = nil, nil
end

return M
