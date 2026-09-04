-- Git, in a floating lazygit window on <leader>g: stage, commit and push
-- without leaving the editor. The lazygit binary itself comes from winget
-- (JesseDuffield.lazygit); this only dresses the window to match everything
-- else.
return {
  {
    "kdheepak/lazygit.nvim",
    cmd = "LazyGit",
    init = function()
      vim.g.lazygit_floating_window_scaling_factor = 0.9
      -- square corners, like every other border here
      vim.g.lazygit_floating_window_border_chars =
        { "┌", "─", "┐", "│", "┘", "─", "└", "│" }
      vim.g.lazygit_floating_window_use_plenary = 0
    end,
  },
}
