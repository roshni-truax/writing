-- The file tree. Closed by default; <leader>e slides it in from the left,
-- rooted at the repo holding the file, or at the file's own folder when
-- there is no repo - lua/writing.lua works out which.
--
-- Opened with no file - `nvim` alone, or `nvim .` in some folder - neovim
-- goes straight to the tree instead of an empty buffer, ready to pick a
-- document or start a new one (init.lua does that part).
return {
  {
    "nvim-neo-tree/neo-tree.nvim",
    branch = "v3.x",
    cmd = "Neotree",
    dependencies = {
      "nvim-lua/plenary.nvim",
      "MunifTanjim/nui.nvim",
      "nvim-tree/nvim-web-devicons",
    },
    opts = {
      close_if_last_window = true,
      popup_border_style = "single",
      enable_git_status = false,
      enable_diagnostics = false,
      window = { position = "left", width = 30 },
      filesystem = {
        bind_to_cwd = false, -- the root is the repo, not wherever :cd wanders
        follow_current_file = { enabled = true },
        filtered_items = { hide_dotfiles = true, hide_gitignored = false },
        commands = {
          -- PDFs are not text, so the tree does not open them as one: they
          -- open in the viewer (writing/viewer - the pdf viewer this repo
          -- grew because nothing else runs in a terminal on Windows), in a
          -- wezterm pane beside the editor, or in a wezterm window of its
          -- own when there is no pane to be had.
          open = function(state)
            local node = state.tree:get_node()
            if node.type == "file" and node.name:lower():match("%.pdf$") then
              -- the viewer ships beside this config; writing.tool works out
              -- how to run it (on the nas that is the shim, which knows its
              -- venv)
              local view = vim.list_extend(require("writing").tool("viewer"), { node.path })
              -- Over ssh to the nas there is no wezterm on this side to hold
              -- a pane: it is the terminal back on the windows machine. Ask
              -- first, because vim.system raises when the command is not
              -- there at all rather than calling back with a code, and an
              -- error is no way to say "open it in your other session".
              if vim.fn.executable("wezterm") == 0 then
                vim.notify("no wezterm here to put the viewer in; run  "
                  .. table.concat(view, " ") .. "  in another session")
                return
              end
              vim.system(
                vim.list_extend({ "wezterm", "cli", "split-pane", "--right", "--percent", "50", "--" }, view),
                {},
                function(out)
                  if out.code ~= 0 then
                    -- inside no wezterm pane, or its mux would not answer:
                    -- a window of the viewer's own instead
                    vim.system(vim.list_extend({ "wezterm", "start", "--" }, view))
                  end
                end
              )
              return
            end
            require("neo-tree.sources.filesystem.commands").open(state)
          end,
        },
      },
      default_component_configs = {
        indent = { with_markers = false },
      },
    },
  },
}
