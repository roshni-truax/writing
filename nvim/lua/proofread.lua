-- Spelling and grammar, on demand: <leader>h - h for harper - starts it on
-- the current file and marks what it finds; <leader>h again stops it and
-- clears the marks.
--
-- harper-ls is a single binary (winget install Automattic.harper-ls), offline
-- and quick, so nothing is sent anywhere and there is no runtime to wait for.
-- It is wired up with Neovim's own LSP client rather than a plugin.
--
-- Nothing is drawn in the margin. A problem shows as an underlined word,
-- coloured by what kind of problem it is; put the cursor on it and the message
-- appears in a small float, the way the rest of this setup keeps chrome out of
-- the way. This is the one place colour is used, and only while a pass is
-- running - <leader>h again and the page is greyscale prose again.
--
-- `gra` on a flagged word offers harper's suggestions, and on a misspelling
-- also "add to the user dictionary" - a permanent dismissal, written to
-- `proofread/dictionary.txt` next to this config so it travels with the repo.
--
-- harper's other dismissal, "ignore this lint", is filtered out below. It
-- writes a file per manuscript keyed to that file's full path, which is state
-- that neither survives a rename nor means anything on another machine. The
-- dictionary is the part worth keeping.
--
-- cmd_cwd is set because harper 2.8 accepts `ignoredLintsPath` and then
-- ignores it, writing to its own working directory instead (tested against
-- absolute paths and a set workspace root). Pointing that at `proofread/`
-- keeps stray files out of the manuscript folder if harper ever writes one.

local M = {}

local state = vim.fn.stdpath("config") .. "/proofread"

-- What kind of problem each mark is, by colour. harper tags every lint with a
-- code - SpellCheck, RepeatedWords, Spaces - and those are sorted into three
-- groups here. Anything harper adds in a future version arrives as grammar,
-- which is the safe default.
local MECHANICS = {
  Spaces = true,
  WrongApostrophe = true,
  UnclosedQuotes = true,
  CorrectNumberSuffix = true,
  Dashes = true,
  EllipsisLength = true,
  TerminatingConjunction = true,
}

-- Severity is the only channel the diagnostic pipeline gives us to carry the
-- category, so it is used as a label rather than as a judgement: nothing here
-- is an "error" in the sense of something being broken.
local function categorise(code)
  if code == "SpellCheck" then
    return vim.diagnostic.severity.ERROR -- spelling
  elseif MECHANICS[code] then
    return vim.diagnostic.severity.INFO -- spacing, quotes, punctuation
  end
  return vim.diagnostic.severity.WARN -- grammar and word choice
end

local config = {
  name = "harper",
  cmd = { "harper-ls", "--stdio" },
  cmd_cwd = state,
  filetypes = { "markdown", "text" },
  root_dir = state,
  handlers = {
    -- harper sends everything at one severity; re-label each mark by its code
    -- on the way in, which is what gives the three colours below.
    ["textDocument/publishDiagnostics"] = function(err, result, ctx)
      for _, diagnostic in ipairs((result or {}).diagnostics or {}) do
        diagnostic.severity = categorise(diagnostic.code)
      end
      return vim.lsp.handlers["textDocument/publishDiagnostics"](err, result, ctx)
    end,

  },
  settings = {
    ["harper-ls"] = {
      userDictPath = state .. "/dictionary.txt",
      dialect = "American",
      -- Everything is a hint: this is a proofreading pass, not an error list.
      diagnosticSeverity = "hint",
      linters = {
        -- The sentence-level rules are off. In fiction they fire constantly on
        -- dialogue, fragments and deliberate repetition, which is noise rather
        -- than proofreading. Turn any of them back on if you want them.
        SentenceCapitalization = false,
        LongSentences = false,
        SpelledNumbers = false,
      },
    },
  },
}

-- How a problem is marked: the word underlined and tinted, nothing else.
--
-- A plain underline, not the usual undercurl. Neovim only emits undercurl if
-- the terminal says it can draw one, and it learns that by asking - the same
-- question Windows' console layer swallows, so the answer never arrives and
-- nothing at all gets drawn. WezTerm can draw undercurls; Neovim just cannot
-- find out. `smul` is in every terminfo, so an underline always lands. The
-- colour is on the word for the same reason: Neovim's Windows build never
-- sends the escape for a coloured underline, and the word's own colour it
-- always does.
--
-- The three colours are zenwritten's own, read out of the theme rather than
-- picked, so they stay muted and follow the light/dark flip on their own:
--
--   spelling    red      the word is not in the dictionary
--   grammar     orange   word choice, repetition, agreement
--   mechanics   blue     spacing, quotes, punctuation
local function marks()
  for _, group in ipairs({ "Error", "Warn", "Info" }) do
    local themed = vim.api.nvim_get_hl(0, { name = "Diagnostic" .. group, link = false })
    vim.api.nvim_set_hl(0, "DiagnosticUnderline" .. group, {
      underline = true,
      fg = themed.fg, -- the word itself carries the colour
    })
  end
end

local function attached()
  return vim.lsp.get_clients({ bufnr = 0, name = "harper" })[1]
end

function M.toggle()
  local client = attached()
  if client then
    vim.lsp.stop_client(client.id)
    vim.diagnostic.reset(nil, 0)
    vim.notify("proofreading off")
    return
  end

  if vim.fn.executable("harper-ls") == 0 then
    vim.notify("harper-ls not found: winget install Automattic.harper-ls", vim.log.levels.ERROR)
    return
  end

  marks()
  vim.diagnostic.config({
    virtual_text = false, -- the message belongs in the float, not the margin
    signs = false,
    underline = true,
    update_in_insert = false,
    float = { border = "single", source = false, header = "" },
  })

  vim.lsp.start(config)

  -- `gra` is Neovim's own code-action key. It is rebound for this buffer only,
  -- to the same thing minus harper's "ignore this lint" action. It has to be
  -- filtered here rather than on the way in: vim.lsp.buf.code_action passes
  -- its own handler, so a handler set on the client never sees the reply.
  vim.keymap.set("n", "gra", function()
    vim.lsp.buf.code_action({
      filter = function(action)
        return not (action.title or ""):match("^Ignore Harper")
      end,
    })
  end, { buffer = true, desc = "proofreading suggestions" })

  vim.notify("proofreading on")
end

-- The message for whatever is under the cursor, after a short pause. Only
-- while harper is attached, so the pause costs nothing the rest of the time.
vim.api.nvim_create_autocmd("CursorHold", {
  callback = function()
    if attached() then
      vim.diagnostic.open_float(nil, { focus = false, scope = "cursor" })
    end
  end,
})

vim.api.nvim_create_autocmd("ColorScheme", {
  callback = function()
    if attached() then
      marks()
    end
  end,
})

vim.keymap.set("n", "<leader>h", M.toggle, { desc = "proofreading on / off" })

return M
