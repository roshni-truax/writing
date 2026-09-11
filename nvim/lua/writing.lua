-- The few facts about this setup that more than one file needs: where the
-- tree should be rooted, where the checkout is, and how to run the python
-- tools that ship beside this config.
local M = {}

-- What the file tree should call the root: the git repo holding the file,
-- when there is one, and otherwise the folder itself. Opening a story roots
-- the tree at that story's folder; opening something inside a repo roots it
-- at the repo.
--
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

-- The checkout this config is part of: printer/, viewer/ and wezterm/ all sit
-- beside nvim/ in it. The config is reached through a junction on Windows
-- and a symlink on the nas, and the link's own parent is neither (AppData
-- there, ~/.config here), so it is resolved before taking the folder above.
function M.repo()
  local config = vim.fn.stdpath("config")
  return vim.fs.dirname(vim.uv.fs_realpath(config) or config)
end

-- How to run one of the repo's python tools - `printer`, `viewer` - as a
-- command, ready for a path or two to be appended.
--
-- On Windows the script is handed to python by path. install.ps1 does put
-- a shim on the PATH, but it is a .cmd, and libuv spawns those unreliably;
-- python and a path is what has always been run here.
--
-- Elsewhere the command setup-nas.sh installs is preferred, because it is
-- the one that knows where the tool's venv is - viewer needs pypdfium2 and
-- pillow. Failing that the script is run directly, so a machine where the
-- install has not been run still exports and still views.
function M.tool(name)
  if vim.fn.has("win32") == 1 then
    return { "python", M.repo() .. "/" .. name .. "/" .. name .. ".py" }
  end
  if vim.fn.executable(name) == 1 then
    return { name }
  end
  return { "python3", M.repo() .. "/" .. name .. "/" .. name .. ".py" }
end

return M
