-- Plain vim settings. The ones that matter most here are the wrapping ones:
-- prose is soft-wrapped and never broken mid-word, and the cursor keys follow
-- what you see on screen rather than what the file says.

local o = vim.opt

-- a blank screen on startup: no intro message, no dashboard plugin
o.shortmess:append("I")

-- prose wrapping
o.linebreak = true          -- break at word boundaries, never mid-word
o.breakindent = true        -- wrapped lines keep the paragraph's indent

-- a quiet screen
o.signcolumn = "no"
o.showmode = false          -- the statusline says the mode
o.laststatus = 3            -- one statusline for the whole window
o.cmdheight = 0             -- no command line until you ask for one (noice)
o.fillchars = { eob = " " } -- no tildes past the end of the buffer
o.scrolloff = 8
o.sidescrolloff = 8

-- completion, which only lua/references.lua uses: a short list beside the
-- word rather than a panel up the side of the screen, nothing inserted
-- until it is chosen, and vim narrowing the list fuzzily as you type
o.pumheight = 5             -- rows, so the popup stays a small inline tab
o.completeopt = "menu,menuone,noinsert,fuzzy"
o.shortmess:append("c")     -- no "match 1 of 33" in the message line

-- writing
o.spelllang = "en_us"
o.spellcapcheck = ""        -- do not nag about capitals mid-sentence in drafts
o.conceallevel = 2          -- render-markdown hides the syntax it draws over

-- behaviour people generally want
o.mouse = "a"
o.clipboard = "unnamedplus" -- a plain y and p are the system clipboard

-- Over ssh there is nothing on the far end to be that clipboard: the nas is
-- headless and has no xclip or anything like it, so a yank went to the `+`
-- register and stopped there. OSC 52 is an escape the terminal reads -
-- neovim writes the text out, wezterm puts it on the desktop's clipboard,
-- and nothing has to be installed on the nas. Neovim is supposed to reach
-- for this itself when $SSH_TTY is set and finds no provider; measured, it
-- does not, so it is said here.
--
-- The copy half only. Wezterm ignores requests to read the clipboard - "52
-- | Manipulate clipboard | Requests to query the clipboard are ignored", in
-- its own escape-sequence table - so nothing can hand the desktop's
-- clipboard back, and no plugin changes that. Pasting from the desktop is
-- wezterm's own ctrl+shift+v, which arrives as a bracketed paste and needs
-- none of this. `"+p` falls back to the last yank, so it does the obvious
-- thing rather than erroring.
if vim.fn.has("win32") == 0 then
  local osc52 = require("vim.ui.clipboard.osc52")
  local function last_yank()
    return { vim.fn.getreg('"', 1, true), vim.fn.getregtype('"') }
  end
  vim.g.clipboard = {
    name = "osc52",
    copy = { ["+"] = osc52.copy("+"), ["*"] = osc52.copy("*") },
    paste = { ["+"] = last_yank, ["*"] = last_yank },
  }
end
o.undofile = true           -- undo survives closing the file
o.swapfile = false
o.ignorecase = true
o.smartcase = true
o.splitbelow = true
o.splitright = true
o.updatetime = 250
o.timeoutlen = 400
o.confirm = true            -- ask rather than refuse when quitting unsaved

-- indentation, for the odd note or config file
o.expandtab = true
o.shiftwidth = 2
o.tabstop = 2
o.smartindent = true

-- briefly highlight yanked text, so you can see what you took
vim.api.nvim_create_autocmd("TextYankPost", {
  callback = function()
    vim.hl.on_yank({ timeout = 150 })
  end,
})

-- reopen a file where you left it
vim.api.nvim_create_autocmd("BufReadPost", {
  callback = function()
    local mark = vim.api.nvim_buf_get_mark(0, [["]])
    if mark[1] > 0 and mark[1] <= vim.api.nvim_buf_line_count(0) then
      pcall(vim.api.nvim_win_set_cursor, 0, mark)
    end
  end,
})
