-- The frontmatter block out of the way while you write.
--
-- Every manuscript and deck opens with a fenced block saying how it is set
-- - spacing, theme, skip-numbering - which is read once and then sits above
-- the first line of the story for the rest of the draft. With the cursor
-- anywhere else the whole block is gone - keys and both fences - and the
-- file opens on its first real line. Put the cursor back on it with `gg`
-- or `:1` and it is all there again.
--
-- The lines are hidden by an extmark, not by a fold: `conceal_lines` takes
-- the line off the screen entirely, where a closed fold would still spend a
-- row on saying it is closed. Markdown only, since nothing else here has
-- frontmatter.

local ns = vim.api.nvim_create_namespace("frontmatter")

-- The two fence rows, 1-based, or nothing if the file does not open with a
-- block. The frontmatter is the fence on the very first line, the same rule
-- printer reads by, so a fenced code block further down is never mistaken
-- for one.
local function fences(buf)
  local first = vim.api.nvim_buf_get_lines(buf, 0, 1, false)[1]
  if not first then
    return
  end
  local fence = first:match("^(```+)%s*$") or first:match("^(~~~+)%s*$")
  if not fence then
    return
  end
  for i, line in ipairs(vim.api.nvim_buf_get_lines(buf, 1, -1, false)) do
    if line:sub(1, 3) == fence:sub(1, 3) then
      return 1, i + 1
    end
  end
end

local function refresh(buf)
  if not vim.api.nvim_buf_is_valid(buf) then
    return
  end
  vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)
  local open, close = fences(buf)
  if not open or close - open < 2 then
    return -- no block, or one with nothing in it to hide
  end
  -- The cursor that counts is the one being typed with. A buffer is often
  -- in more than one window - writing mode is a floating window over the
  -- one the file was already open in, and that one keeps its own cursor
  -- wherever it was parked - so asking every window whether it sits in the
  -- block answers yes forever from a window nobody is looking at. That is
  -- exactly what left the block on screen in writing mode.
  local windows = vim.api.nvim_get_current_buf() == buf
      and { vim.api.nvim_get_current_win() }
      or vim.fn.win_findbuf(buf)
  for _, win in ipairs(windows) do
    local row = vim.api.nvim_win_get_cursor(win)[1]
    if row >= open and row <= close then
      return
    end
  end
  for row = open - 1, close - 1 do -- the block, fences and all, 0-based
    vim.api.nvim_buf_set_extmark(buf, ns, row, 0, { conceal_lines = "" })
  end
end

vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function(args)
    refresh(args.buf)
    vim.api.nvim_create_autocmd(
      { "CursorMoved", "CursorMovedI", "TextChanged", "TextChangedI", "BufWinEnter" },
      {
        buffer = args.buf,
        callback = function()
          refresh(args.buf)
        end,
      }
    )
  end,
})
