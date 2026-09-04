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

-- writing
o.spelllang = "en_us"
o.spellcapcheck = ""        -- do not nag about capitals mid-sentence in drafts
o.conceallevel = 2          -- render-markdown hides the syntax it draws over

-- behaviour people generally want
o.mouse = "a"
o.clipboard = "unnamedplus"
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
