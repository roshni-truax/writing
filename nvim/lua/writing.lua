-- What the file tree should call the root: the git repo holding the file,
-- when there is one, and otherwise the folder itself. Opening a story roots
-- the tree at that story's folder; opening something inside a repo roots it
-- at the repo.
local M = {}

-- The root for `path`, which defaults to the current file, or to where we
-- stand when the buffer has no file behind it.
function M.root(path)
  if path == nil then
    path = vim.api.nvim_buf_get_name(0)
    if path == "" or vim.bo.buftype ~= "" then
      path = vim.uv.cwd()
    end
  end
  return vim.fs.root(path, ".git")
    or (vim.fn.isdirectory(path) == 1 and path or vim.fs.dirname(path))
end

return M
