-- Sources, from the editor's side: `{{` offers the ones this document has,
-- and a key it does not know opens a form to add it.
--
-- The sources themselves live in references.json beside the document, or
-- wherever its frontmatter points, and printer reads the same file when it
-- sets the pdf - see printer/references.py for the shapes and the Chicago
-- notes built from them.
--
-- Completion is neovim's own. A list of a few dozen sources needs none of
-- the machinery a completion plugin brings, and `vim.fn.matchfuzzy` already
-- does the matching; this way the popup is the one the theme already
-- colours, and there is no plugin to pin.
local M = {}

local TYPES = { "book", "article", "chapter", "website", "thesis", "report" }

-- The fields each kind of source carries, in the order the form asks for
-- them. `author` and its like hold a list, one name per line in the file;
-- the form takes them separated by "; ".
local FIELDS = {
  book = { "author", "title", "volume", "edition", "translator", "place", "publisher", "year", "isbn" },
  report = { "author", "title", "place", "publisher", "year" },
  article = { "author", "title", "journal", "volume", "issue", "year", "pages", "doi" },
  chapter = { "author", "title", "book", "editor", "pages", "place", "publisher", "year" },
  website = { "author", "title", "site", "date", "url" },
  thesis = { "author", "title", "kind", "school", "year" },
}
local LISTS = { author = true, editor = true, translator = true }
-- how wide the source beside the key may be. a title runs to any length -
-- "Specters of Marx: The State of the Debt, the Work of Mourning and the
-- New International" - and the popup is as wide as its widest row, so
-- without this it reaches across the screen
local MENU = 40

-- ---------------------------------------------------------------- the file --

-- Where this buffer's sources are: what the frontmatter names, else
-- references.json beside the document. The frontmatter is the fenced block
-- on the first line, so only the top of the buffer is read.
local function path_for(buf)
  local name = vim.api.nvim_buf_get_name(buf)
  if name == "" then
    return nil
  end
  local dir = vim.fs.dirname(name)
  local head = vim.api.nvim_buf_get_lines(buf, 0, 40, false)
  if head[1] and head[1]:match("^```%s*$") then
    for i = 2, #head do
      if head[i]:match("^```") then
        break
      end
      local named = head[i]:match("^references:%s*(.-)%s*$")
      if named and named ~= "" then
        return vim.fs.normalize(dir .. "/" .. named)
      end
    end
  end
  return dir .. "/references.json"
end

local function read(path)
  local f = path and io.open(path, "r")
  if not f then
    return {}
  end
  local text = f:read("a")
  f:close()
  local ok, entries = pcall(vim.json.decode, text)
  if not ok or type(entries) ~= "table" then
    vim.notify("references: " .. vim.fs.basename(path) .. " is not readable json",
      vim.log.levels.ERROR)
    return {}
  end
  return entries
end

local function write(path, entries)
  -- sorted keys, two-space indent: the file is read by people as well as by
  -- printer, and a stable order keeps its diffs to what actually changed
  local keys = vim.tbl_keys(entries)
  table.sort(keys)
  local out = { "{" }
  for i, key in ipairs(keys) do
    local entry, fields = entries[key], {}
    local order = FIELDS[entry.type] or {}
    local written = { type = true }
    table.insert(fields, ('    "type": %s'):format(vim.json.encode(entry.type)))
    for _, field in ipairs(order) do
      if entry[field] ~= nil and entry[field] ~= "" then
        table.insert(fields, ('    "%s": %s'):format(field, vim.json.encode(entry[field])))
        written[field] = true
      end
    end
    for field, value in pairs(entry) do  -- anything the form did not ask for
      if not written[field] then
        table.insert(fields, ('    "%s": %s'):format(field, vim.json.encode(value)))
      end
    end
    table.insert(out, ('  "%s": {'):format(key))
    table.insert(out, table.concat(fields, ",\n"))
    table.insert(out, i == #keys and "  }" or "  },")
  end
  table.insert(out, "}")
  local f = assert(io.open(path, "w"))
  f:write(table.concat(out, "\n"), "\n")
  f:close()
end

-- ------------------------------------------------------------- completion --

-- The surname a source sorts and reads under, the same rule references.py
-- follows: a trailing comma means a body, a comma means the surname is
-- already first, and otherwise it is the last word.
local function surname(name)
  if name:match(",%s*$") then
    return (name:gsub(",%s*$", ""))
  end
  if name:find(",") then
    return vim.trim(name:match("^([^,]+)"))
  end
  return name:match("(%S+)%s*$") or name
end

local function shorten(text, width)
  if vim.fn.strchars(text) <= width then
    return text
  end
  return vim.fn.strcharpart(text, 0, width - 1) .. "…"
end

-- What a source reads as in the popup: the key to insert, and just enough
-- of the source beside it to tell two of them apart - a surname and a
-- title, cut to `MENU`. The whole of both is still matched against.
local function items(entries, base)
  local rows = {}
  for key, entry in pairs(entries) do
    local who = entry.author and entry.author[1] and surname(entry.author[1]) or ""
    local title = entry["short-title"] or entry.title or ""
    local menu = vim.trim((who ~= "" and (who .. " · ") or "") .. title)
    table.insert(rows, {
      key = key,
      menu = shorten(menu, MENU),
      hay = key .. " " .. menu .. " " .. (entry.title or ""),
    })
  end
  table.sort(rows, function(a, b) return a.key < b.key end)

  if base ~= "" then
    local hay = vim.tbl_map(function(r) return r.hay end, rows)
    local matched = vim.fn.matchfuzzy(hay, base)
    local order, out = {}, {}
    for i, text in ipairs(matched) do order[text] = i end
    for _, r in ipairs(rows) do
      if order[r.hay] then table.insert(out, r) end
    end
    table.sort(out, function(a, b) return order[a.hay] < order[b.hay] end)
    rows = out
  end

  return vim.tbl_map(function(r)
    return { word = r.key, abbr = r.key, menu = r.menu, icase = 1, dup = 0 }
  end, rows)
end

-- The `{{` the cursor sits inside, and what has been typed since it. nil
-- when the cursor is not in one.
local function context()
  local line = vim.api.nvim_get_current_line()
  local col = vim.fn.col(".") - 1
  local before = line:sub(1, col)
  local start, base = before:match("()%{%{([^{}]*)$")
  if not start or before:sub(start - 1, start - 1) == "\\" then
    return nil
  end
  return start + 2, base
end

-- Neovim's own completion does the filtering, so this hands over the whole
-- list once and then keeps out of the way. Anything else fights the typing:
-- rebuilding the popup on every keystroke swallows both a refinement and a
-- note written in your own words, and eats a delete along with them.
function M.completefunc(findstart, _)
  if findstart == 1 then
    local at = context()
    if not at then
      return -3  -- not in a {{, so no completion and no message
    end
    return at - 1  -- completefunc counts from 0, `context` from 1
  end
  local entries = read(path_for(0))
  if vim.tbl_isempty(entries) then
    return {}
  end
  return items(entries, "")
end

-- Open it the moment `{{` is finished, and never again: from there vim
-- narrows the list as you type, closes it when nothing matches - which is
-- what typing a note of your own does - and reopens only if you come back
-- to a bare `{{`.
local function trigger()
  if vim.fn.mode() ~= "i" then
    return
  end
  local line = vim.api.nvim_get_current_line()
  local before = line:sub(1, vim.fn.col(".") - 1)
  if vim.fn.pumvisible() == 1 then
    -- a key never has a space in it, so the first one says this is a note
    -- in your own words and the list has nothing to offer it
    local base = before:match("%{%{([^{}]*)$")
    if base and base:find(" ") then
      vim.api.nvim_feedkeys(vim.keycode("<C-e>"), "n", false)
    end
    return
  end
  if before:sub(-2) == "{{" and before:sub(-3, -3) ~= "\\" then
    vim.api.nvim_feedkeys(vim.keycode("<C-x><C-u>"), "n", false)
  end
end

-- ------------------------------------------------------------------ the form --

local form = {}

-- Nothing but the fields: what the keys do is in this file, not on screen.
local function lines_for(kind, values, key)
  local out = {
    ("  %-10s %s"):format("key", key),
    ("  %-10s %s"):format("type", kind),
    "",
  }
  for _, field in ipairs(FIELDS[kind] or {}) do
    out[#out + 1] = ("  %-10s %s"):format(field, values[field] or "")
  end
  return out
end

local function values_from(buf)
  local values, kind, key = {}, nil, nil
  for _, line in ipairs(vim.api.nvim_buf_get_lines(buf, 0, -1, false)) do
    local field, value = line:match("^  (%S+)%s+(.-)%s*$")
    if field then
      if field == "type" then
        kind = value
      elseif field == "key" then
        key = value
      elseif value ~= "" then
        values[field] = value
      end
    end
  end
  return key, kind, values
end

-- The value column of every field line, so tab can step between them.
local function field_rows(buf)
  local rows = {}
  for i, line in ipairs(vim.api.nvim_buf_get_lines(buf, 0, -1, false)) do
    if line:match("^  %S+%s") then
      rows[#rows + 1] = i - 1
    end
  end
  return rows
end

local function step(buf, win, delta)
  local rows = field_rows(buf)
  local at = vim.api.nvim_win_get_cursor(win)[1] - 1
  local index = 1
  for i, row in ipairs(rows) do
    if row == at then index = i end
  end
  index = index + delta
  if index < 1 then index = #rows end
  if index > #rows then index = 1 end
  local row = rows[index]
  local line = vim.api.nvim_buf_get_lines(buf, row, row + 1, false)[1]
  vim.api.nvim_win_set_cursor(win, { row + 1, #line })
end

-- ------------------------------------------------------------------ lookup --

local function fetch(buf, win)
  local _, kind, values = values_from(buf)
  local doi, isbn = values.doi, values.isbn
  if not doi and not isbn then
    vim.notify("references: fill in doi or isbn first")
    return
  end
  local url = doi
    and ("https://api.crossref.org/works/" .. doi)
    or ("https://openlibrary.org/api/books?bibkeys=ISBN:" .. isbn .. "&format=json&jscmd=data")
  vim.notify("references: looking it up…")
  vim.system({ "curl", "-sL", "--max-time", "20", url }, { text = true }, function(out)
    vim.schedule(function()
      if out.code ~= 0 or out.stdout == "" then
        vim.notify("references: the lookup did not answer", vim.log.levels.ERROR)
        return
      end
      local ok, data = pcall(vim.json.decode, out.stdout)
      if not ok then
        vim.notify("references: the lookup answered with something unreadable",
          vim.log.levels.ERROR)
        return
      end
      local found = doi and M.from_crossref(data) or M.from_openlibrary(data, isbn)
      if not found then
        vim.notify("references: nothing found for that " .. (doi and "doi" or "isbn"),
          vim.log.levels.WARN)
        return
      end
      form.open(form.key, found.type or kind, vim.tbl_extend("force", values, found), form.path)
      vim.notify("references: filled in from " .. (doi and "crossref" or "open library"))
    end)
  end)
end

-- Crossref's shape, which is the one a doi answers with.
function M.from_crossref(data)
  local m = data and data.message
  if not m then
    return nil
  end
  local authors = {}
  for _, person in ipairs(m.author or {}) do
    if person.family then
      table.insert(authors, person.given and (person.given .. " " .. person.family) or person.family)
    end
  end
  local year = m.issued and m.issued["date-parts"] and m.issued["date-parts"][1]
    and m.issued["date-parts"][1][1]
  return {
    type = "article",
    author = #authors > 0 and table.concat(authors, "; ") or nil,
    title = m.title and m.title[1],
    journal = m["container-title"] and m["container-title"][1],
    volume = m.volume,
    issue = m.issue,
    pages = m.page,
    year = year and tostring(year) or nil,
  }
end

-- Open Library's, which is the one an isbn answers with.
function M.from_openlibrary(data, isbn)
  local book = data and data["ISBN:" .. isbn]
  if not book then
    return nil
  end
  local authors = {}
  for _, person in ipairs(book.authors or {}) do
    table.insert(authors, person.name)
  end
  local publisher = book.publishers and book.publishers[1] and book.publishers[1].name
  local place = book.publish_places and book.publish_places[1] and book.publish_places[1].name
  return {
    type = "book",
    author = #authors > 0 and table.concat(authors, "; ") or nil,
    title = book.title,
    publisher = publisher,
    place = place,
    year = book.publish_date and book.publish_date:match("(%d%d%d%d)") or nil,
  }
end

-- ------------------------------------------------------------------ opening --

function form.open(key, kind, values, path)
  -- the document's own references file, caught before the float takes
  -- focus: from inside the form, the current buffer is the form
  form.path = path or form.path or path_for(0)
  form.key, form.kind, form.values = key, kind or "book", values or {}
  if form.win and vim.api.nvim_win_is_valid(form.win) then
    vim.api.nvim_win_close(form.win, true)
  end
  local buf = vim.api.nvim_create_buf(false, true)
  local lines = lines_for(form.kind, form.values, key)
  local width = 0
  for _, line in ipairs(lines) do
    width = math.max(width, #line)
  end
  width = math.max(width + 2, 46)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
  vim.bo[buf].buftype = "nofile"
  vim.bo[buf].filetype = "references"

  local win = vim.api.nvim_open_win(buf, true, {
    relative = "editor",
    width = width,
    height = #lines,
    row = math.max(0, math.floor((vim.o.lines - #lines) / 2) - 1),
    col = math.max(0, math.floor((vim.o.columns - width) / 2)),
    style = "minimal",
    border = "single", -- square corners, like every other border here
  })
  form.buf, form.win = buf, win
  vim.wo[win].wrap = false
  -- the label at the head of each line, bold; a window match rather than
  -- marks, so it holds still while the values are typed into
  vim.fn.matchadd("ReferenceLabel", [[^\s\+\zs[a-z-]\+]], 10, -1, { window = win })

  local function close()
    if vim.api.nvim_win_is_valid(win) then
      vim.api.nvim_win_close(win, true)
    end
  end

  local map = function(mode, lhs, fn)
    vim.keymap.set(mode, lhs, fn, { buffer = buf, nowait = true })
  end
  map({ "n", "i" }, "<Tab>", function() step(buf, win, 1) end)
  map({ "n", "i" }, "<S-Tab>", function() step(buf, win, -1) end)
  map({ "n", "i" }, "<C-f>", function() fetch(buf, win) end)
  map({ "n", "i" }, "<C-s>", function() form.save(close) end)
  map("n", "<Esc>", close)
  map("n", "q", close)

  -- the type line changes which fields are asked for, so the form is redrawn
  -- when it is left
  vim.api.nvim_create_autocmd("TextChanged", {
    buffer = buf,
    callback = function()
      local _, kind_now, values_now = values_from(buf)
      if kind_now ~= form.kind and vim.tbl_contains(TYPES, kind_now) then
        form.open(form.key, kind_now, values_now, form.path)
      end
    end,
  })

  step(buf, win, 1)
  vim.cmd.startinsert({ bang = true })
end

function form.save(close)
  local key, kind, values = values_from(form.buf)
  if not key or key == "" then
    vim.notify("references: the source needs a key", vim.log.levels.ERROR)
    return
  end
  if not vim.tbl_contains(TYPES, kind) then
    vim.notify("references: type is one of " .. table.concat(TYPES, ", "), vim.log.levels.ERROR)
    return
  end
  local entry = { type = kind }
  for _, field in ipairs(FIELDS[kind]) do
    local value = values[field]
    if value and value ~= "" then
      if LISTS[field] then
        entry[field] = vim.split(value, "%s*;%s*")
      else
        entry[field] = value
      end
    end
  end
  local path = form.path
  if not path then
    vim.notify("references: save the document first, so there is a folder to write beside",
      vim.log.levels.ERROR)
    return
  end
  local entries = read(path)
  entries[key] = entry
  write(path, entries)
  close()
  vim.notify("references: added " .. key .. " to " .. vim.fs.basename(path))
end

-- --------------------------------------------------------------- the keys --

-- Tab, in a markdown buffer: take the completion if the popup is up, open
-- the form on a `{{` key that has no source, and otherwise be a tab.
function M.tab()
  if vim.fn.pumvisible() == 1 then
    -- tab settles the key either way: it takes the source the list has
    -- landed on, and on one the list does not know it opens the form.
    -- the arrows move between them, which is what they are for.
    return "<C-y>"
  end
  local at, base = context()
  if at and base ~= "" and not read(path_for(0))[base] then
    local path = path_for(0)
    vim.schedule(function()
      form.open(base, "book", {}, path)
    end)
    return ""
  end
  return "<Tab>"
end

local function label_highlight()
  -- bold, and the ink it inherits, so it follows a light/dark flip
  vim.api.nvim_set_hl(0, "ReferenceLabel", { bold = true })
end

function M.setup()
  label_highlight()
  vim.api.nvim_create_autocmd("ColorScheme", { callback = label_highlight })
  vim.api.nvim_create_autocmd("FileType", {
    pattern = "markdown",
    callback = function(args)
      vim.bo[args.buf].completefunc = "v:lua.require'references'.completefunc"
      vim.keymap.set("i", "<Tab>", M.tab, { buffer = args.buf, expr = true, desc = "source, or a tab" })
      vim.api.nvim_create_autocmd("TextChangedI", { buffer = args.buf, callback = trigger })
    end,
  })
end

M.form = form
M.path_for = path_for
M.read = read
M.write = write
M.items = items
M.FIELDS = FIELDS
M.TYPES = TYPES

return M
