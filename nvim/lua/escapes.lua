-- A markdown escape drawn as the character it stands for.
--
-- `\[` is how to write a bracket that markdown must not read as anything:
-- a bare `[words]` is a link reference, and the theme sets its label bold,
-- so a bracketed aside comes out looking like a link that was never made.
-- The escape fixes the meaning but leaves a backslash on the screen, which
-- is the wrong thing to be reading a paragraph through.
--
-- So the backslash is hidden and the character it protects is left: the
-- line reads as it will print. The line the cursor is on shows its
-- backslashes, the way the frontmatter block opens, so what is actually in
-- the file is never more than a keystroke away.
--
-- Treesitter finds them, not a pattern: it knows `\\` is an escaped
-- backslash rather than an escape of the character after it, and it never
-- looks inside a code block. Only the rows on screen are marked, since a
-- manuscript is long and nothing off screen is being read.

local ns = vim.api.nvim_create_namespace("escapes")

-- Asked for the first time a markdown file is drawn, not while this file is
-- being read: `query.parse` asserts that the language's parser is loaded,
-- and at startup markdown_inline's may not be yet. Parsing it up here threw
-- "No parser for language" out of init.lua, which took render-markdown and
-- everything else after line 99 down with it - and only sometimes, since
-- whether the parser is loaded by then depends on what has already been
-- opened.
local query
local function escapes()
  if query == nil then
    local ok, parsed = pcall(vim.treesitter.query.parse,
      "markdown_inline", "(backslash_escape) @escape")
    query = ok and parsed or false
  end
  return query or nil
end

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
  local cursor = vim.api.nvim_win_get_cursor(win)[1] - 1
  local first = vim.fn.line("w0", win) - 1
  local last = vim.fn.line("w$", win)
  local found = escapes()
  local ok, parser = pcall(vim.treesitter.get_parser, buf, "markdown")
  if not found or not ok or not parser then
    return
  end
  parser:parse({ first, last })
  parser:for_each_tree(function(tree, language)
    if language:lang() ~= "markdown_inline" then
      return
    end
    for _, node in found:iter_captures(tree:root(), buf, first, last) do
      local row, col = node:range()
      if row ~= cursor then
        -- only the backslash: `conceallevel` is 3 here, where a
        -- replacement character is hidden along with what it replaces
        -- (measured - the brackets vanished), so the character the escape
        -- protects has to be the buffer's own. It draws as prose because
        -- `@string.escape.markdown_inline` is Normal in the theme; an
        -- attribute a highlight sets cannot be unset by a mark over it.
        vim.api.nvim_buf_set_extmark(buf, ns, row, col, {
          end_col = col + 1,
          conceal = "",
        })
      end
    end
  end)
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
      "WinScrolled",
      "WinResized",
    }, {
      buffer = args.buf,
      callback = function()
        refresh(args.buf)
      end,
    })
  end,
})
