-- A scene break with something written in it:
--
--     --- the next morning ---
--
-- drawn in the buffer as a rule the width of the window with the words
-- sitting in a gap in the middle, the same faded ink the plain `---` is
-- drawn in. Move the cursor onto the line and the dashes come back, the
-- way the frontmatter block opens.
--
-- Markdown has no such thing - it reads the line as a paragraph - so
-- nothing renders it and printer turns it into raw typst on the way to the
-- pdf (see printer/header.typ). A plain `---` is left to render-markdown,
-- which already draws it, and stays the short centred stroke in print.

local ns = vim.api.nvim_create_namespace("dividers")
local LABELLED = "^%-%-%-+%s+(.-)%s+%-%-%-+$"
local RULE = "─"
local INK = "RenderMarkdownDash" -- the group the plain break is drawn in

local function refresh(buf)
  if not vim.api.nvim_buf_is_valid(buf) then
    return
  end
  vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)
  local win = vim.api.nvim_get_current_buf() == buf and vim.api.nvim_get_current_win()
      or vim.fn.win_findbuf(buf)[1]
  if not win then
    return
  end
  local cursor = vim.api.nvim_win_get_cursor(win)[1]
  local width = vim.api.nvim_win_get_width(win)
  local fence = nil
  for i, line in ipairs(vim.api.nvim_buf_get_lines(buf, 0, -1, false)) do
    local mark = line:match("^%s*(```+)") or line:match("^%s*(~~~+)")
    if fence then
      if mark and mark:sub(1, 1) == fence:sub(1, 1) and #mark >= #fence then
        fence = nil
      end
    elseif mark then
      fence = mark
    else
      local label = line:match(LABELLED)
      -- the line the cursor is on stays as it was typed, so the label can
      -- be edited without fighting the drawing
      if label and i ~= cursor then
        local words = " " .. label .. " "
        local dashes = width - vim.fn.strdisplaywidth(words)
        if dashes >= 2 then
          local left = math.floor(dashes / 2)
          vim.api.nvim_buf_set_extmark(buf, ns, i - 1, 0, {
            end_col = #line,
            conceal = "",
            virt_text = {
              { RULE:rep(left) .. words .. RULE:rep(dashes - left), INK },
            },
            virt_text_pos = "overlay",
          })
        end
      end
    end
  end
end

vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function(args)
    refresh(args.buf)
    vim.api.nvim_create_autocmd({
      "CursorMoved",
      "CursorMovedI",
      "TextChanged",
      "TextChangedI",
      "BufWinEnter",
      "WinResized",
      "VimResized",
    }, {
      buffer = args.buf,
      callback = function()
        refresh(args.buf)
      end,
    })
  end,
})
