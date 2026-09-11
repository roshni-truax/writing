-- Markdown to pdf, on <leader>p. The pdf lands next to the source file with
-- the same name; the viewer, if it has the old one open, notices and
-- re-renders.
--
-- Everything about the conversion lives in writing/printer, beside this
-- config: the page and the type, the blank lines markdown would otherwise
-- collapse, and slides, which sets a deck instead when the frontmatter says
-- `slides: true`. This end only saves the buffer, hands the file over, and
-- says how it went. See printer/printer.py for what it reads.
local M = {}

function M.export()
  -- Save first, so the pdf reflects the buffer as it looks now. `update`
  -- rather than `write`: it skips the disk touch when nothing changed.
  vim.cmd.update()
  local source = vim.fn.expand("%:p")
  local cmd = vim.list_extend(require("writing").tool("printer"), { source })
  vim.system(cmd, { text = true }, function(out)
    vim.schedule(function()
      if out.code ~= 0 then
        vim.notify(out.stderr, vim.log.levels.ERROR)
      elseif out.stderr ~= "" then
        vim.notify(out.stderr, vim.log.levels.WARN)
      else
        vim.notify(vim.trim(out.stdout))
      end
    end)
  end)
end

vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function()
    vim.keymap.set("n", "<leader>p", M.export, { buffer = true, desc = "export pdf" })
  end,
})

return M
