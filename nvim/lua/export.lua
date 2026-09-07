-- Markdown to pdf, on <leader>p. The pdf lands next to the source file with
-- the same name; tpv, if it has the old one open, notices and re-renders.
--
-- The conversion is pandoc with typst as the typesetter (both installed with
-- winget; no LaTeX anywhere). The page is A5 with margins in paperback
-- territory, at 10pt with the screen's 1.15 line height. All the type - the
-- terminal's family at ExtraLight, slightly tightened tracking, bold as
-- ExtraBold to match wezterm - lives in export/header.typ, which pandoc
-- injects.
--
-- A file whose frontmatter says `slides: true` is a slide deck instead, and
-- goes through slides/slides.py (beside this config), which has its own
-- page and type; see its docstring for what it reads.
local M = {}

local config = vim.fn.stdpath("config")

local function is_deck()
  local head = vim.api.nvim_buf_get_lines(0, 0, 20, false)
  if head[1] ~= "---" then return false end
  for i = 2, #head do
    if head[i] == "---" then return false end
    if head[i]:match("^slides:%s*true%s*$") then return true end
  end
  return false
end

function M.export()
  -- Save first, so the pdf reflects the buffer as it looks now. `update`
  -- rather than `write`: it skips the disk touch when nothing changed.
  vim.cmd.update()
  local source = vim.fn.expand("%:p")
  local pdf = vim.fn.fnamemodify(source, ":r") .. ".pdf"
  local cmd
  if is_deck() then
    cmd = { "python", vim.fs.dirname(config) .. "/slides/slides.py", source, "-o", pdf }
  else
    cmd = {
      "pandoc",
      source,
      "--output=" .. pdf,
      "--pdf-engine=typst",
      -- An image on its own line is just an image. Pandoc's default is to
      -- promote it to a numbered figure and reprint the alt text underneath
      -- as a caption, which reads as "Figure 1: ..." in the pdf. The alt
      -- text survives this as alt text; it just stops being printed.
      "-f", "markdown-implicit_figures",
      -- code blocks, should any appear, stay greyscale
      "--syntax-highlighting=monochrome",
      -- export/meta.yaml holds the page: A5, margins, size, line height.
      -- It has to be a file because the margins are nested, and pandoc's
      -- -V flags cannot express nesting - dotted names like margin.x are
      -- accepted silently and then never reach the template.
      "--metadata-file=" .. config .. "/export/meta.yaml",
      "--include-in-header=" .. config .. "/export/header.typ",
    }
  end
  vim.system(cmd, {
    -- From the manuscript's own directory, not wherever nvim was started:
    -- a raw-typst image like `#imagepage("map.png")` passes through pandoc
    -- untouched, and typst resolves it against the intermediate .typ
    -- file, which lands in the pandoc process's cwd.
    cwd = vim.fs.dirname(source),
    text = true,
  }, function(out)
    vim.schedule(function()
      if out.code ~= 0 then
        vim.notify(out.stderr, vim.log.levels.ERROR)
      elseif out.stderr ~= "" then
        vim.notify(out.stderr, vim.log.levels.WARN)
      else
        vim.notify("exported " .. vim.fn.fnamemodify(pdf, ":t"))
      end
    end)
  end)
end

vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function()
    vim.keymap.set("n", "<leader>p", M.export, { buffer = true, desc = "export pdf" })
  end,
})

return M
