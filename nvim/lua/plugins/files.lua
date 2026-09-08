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
          -- open in tpv (writing/tpv - the pdf viewer this repo grew
          -- because nothing else runs in a terminal on Windows), in a
          -- wezterm pane beside the editor, or in a wezterm window of its
          -- own when there is no pane to be had.
          open = function(state)
            local node = state.tree:get_node()
            if node.type == "file" and node.name:lower():match("%.pdf$") then
              -- tpv ships beside this config, one level up from the real
              -- nvim folder behind the junction
              -- (on the nas, `tpv` on the path runs it through its venv; the
              -- wezterm pane it wants is still on the far side of ssh, so
              -- there this only reports that wezterm is missing)
              local config = vim.uv.fs_realpath(vim.fn.stdpath("config")) or vim.fn.stdpath("config")
              local view = vim.fn.has("win32") == 1
                and { "python", vim.fs.dirname(config) .. "/tpv/tpv.py", node.path }
                or { "tpv", node.path }
              vim.system(
                vim.list_extend({ "wezterm", "cli", "split-pane", "--right", "--percent", "50", "--" }, view),
                {},
                function(out)
                  if out.code ~= 0 then
                    -- not inside wezterm, or its mux would not answer:
                    -- a window of tpv's own instead
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
