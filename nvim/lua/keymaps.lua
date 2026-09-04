local map = vim.keymap.set

-- Move by what is on screen, not by what is in the file. With soft-wrapped
-- prose a "line" is often a whole paragraph, and without this j and k jump
-- over the whole thing at once.
map({ "n", "x" }, "j", "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true })
map({ "n", "x" }, "k", "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true })
map({ "n", "x" }, "<Down>", "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true })
map({ "n", "x" }, "<Up>", "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true })

-- the file tree, in and out from the left, rooted at the repo or the folder
map("n", "<leader>e", function()
  require("neo-tree.command").execute({ toggle = true, dir = require("writing").root() })
end, { desc = "file tree" })

-- git, in a floating lazygit window
map("n", "<leader>g", "<cmd>LazyGit<cr>", { desc = "lazygit" })

-- rendered markdown <-> the raw text, for this buffer only
map("n", "<leader>m", "<cmd>RenderMarkdown buf_toggle<cr>", { desc = "rendered / raw markdown" })

-- spell check off by default; this turns it on for the current file when you
-- want a proofreading pass, and off again after
map("n", "<leader>s", function()
  vim.opt_local.spell = not vim.wo.spell
  vim.notify("spell " .. (vim.wo.spell and "on" or "off"))
end, { desc = "spell check on / off" })

-- light and dark, one key
map("n", "<leader>b", function()
  vim.o.background = vim.o.background == "dark" and "light" or "dark"
end, { desc = "light / dark" })

-- the everyday two
map("n", "<leader>w", "<cmd>write<cr>", { desc = "write" })
map("n", "<leader>q", "<cmd>quit<cr>", { desc = "quit" })

-- delete into the black-hole register: with clipboard=unnamedplus a plain d
-- overwrites the system clipboard, and this one throws the text away instead
map({ "n", "x" }, "<leader>d", '"_d', { desc = "delete, keep clipboard" })

-- clear the search highlight
map("n", "<Esc>", "<cmd>nohlsearch<cr>", { silent = true })

-- keep the cursor put when joining, and centred when jumping
map("n", "J", "mzJ`z")
map("n", "<C-d>", "<C-d>zz")
map("n", "<C-u>", "<C-u>zz")

-- move between splits without the leading <C-w>
map("n", "<C-h>", "<C-w>h")
map("n", "<C-j>", "<C-w>j")
map("n", "<C-k>", "<C-w>k")
map("n", "<C-l>", "<C-w>l")

-- Splits, mirroring the wezterm pane keys one layer in: alt acts on panes
-- outside, ctrl on splits inside, the same letters throughout. s and v echo
-- :sp and :vs the way alt+s and alt+v do out there; x closes (quietly a
-- no-op on the last window); z zooms, and puts the layout back the second
-- time.
--
-- Visual block is not lost to ctrl+v: vim has always kept ctrl+q as its
-- synonym (:h CTRL-Q), so taking the key costs a spelling, not a feature.
map("n", "<C-s>", "<cmd>split<cr>", { desc = "split below" })
map("n", "<C-v>", "<cmd>vsplit<cr>", { desc = "split beside" })
map("n", "<C-x>", function()
  pcall(vim.cmd.close)
end, { desc = "close split" })

local zoomed
map("n", "<C-z>", function()
  if zoomed then
    vim.cmd(zoomed)
    zoomed = nil
  else
    zoomed = vim.fn.winrestcmd()
    vim.cmd("wincmd _")
    vim.cmd("wincmd |")
  end
end, { desc = "zoom split" })

-- Resize on ctrl+arrows, paired with alt+arrows outside. Shifted letters
-- would have matched wezterm exactly, but Windows' console layer hands
-- ctrl+shift+h to neovim as plain ctrl+h and drops ctrl+shift+arrow
-- outright (both measured, not guessed); plain ctrl+arrows arrive intact.
map("n", "<C-Up>", "<cmd>resize +2<cr>", { desc = "split taller" })
map("n", "<C-Down>", "<cmd>resize -2<cr>", { desc = "split shorter" })
map("n", "<C-Left>", "<cmd>vertical resize -2<cr>", { desc = "split narrower" })
map("n", "<C-Right>", "<cmd>vertical resize +2<cr>", { desc = "split wider" })
