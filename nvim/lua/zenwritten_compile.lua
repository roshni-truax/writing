-- Compiles zenwritten from its lush source into plain highlight tables.
--
-- The lush pipeline built the same colours from source on every startup,
-- at ~45ms a time. This bakes the result - every highlight group, the
-- terminal palette and the lualine theme, in both backgrounds - into
-- generated files that load in a couple of milliseconds:
--
--   colors/zenwritten.lua              the colorscheme itself
--   lua/lualine/themes/zenwritten.lua  the statusline's colours
--   ../wezterm/zenwritten.lua          the terminal's colours, same source
--
-- The theme's configuration lives here, because it has to be set before
-- compiling to reach the output. After changing it, or updating the
-- zenbones plugin, or neovim, recompile with
--
--   :lua require("zenwritten_compile").compile()
--
-- and commit the regenerated files.
local M = {}

local CONFIG = {
  darkness = "stark",
  transparent_background = false,
}

-- groups for plugins this setup does not have. zenbones sets them all;
-- nothing here reads them
local ABSENT = {
  "Nvim", "@lsp.", "Coc", "Fzf", "Mason", "Notify", "Mini", "Neogit", "Cmp", "Blink",
  "Telescope", "WhichKey", "Hop", "Buffer", "Trouble", "Sneak", "Flash", "Ibl", "Indent",
  "Snacks", "Nnn", "Git", "Lsp", "Redraw", "Snippet", "Compl", "diff", "help",
}

local function absent(name)
  if name:match("%.vimdoc$") then
    return true
  end
  for _, prefix in ipairs(ABSENT) do
    if vim.startswith(name, prefix) then
      return true
    end
  end
  return false
end

-- blend two packed 0xRRGGBB colours. t = 0 gives a, t = 1 gives b
local function mix(a, b, t)
  local function part(n, shift)
    return math.floor(n / shift) % 256
  end
  local r = part(a, 65536) + (part(b, 65536) - part(a, 65536)) * t
  local g = part(a, 256) + (part(b, 256) - part(a, 256)) * t
  local bl = part(a, 1) + (part(b, 1) - part(a, 1)) * t
  return math.floor(r + 0.5) * 65536 + math.floor(g + 0.5) * 256 + math.floor(bl + 0.5)
end

-- what the markdown and leap plugins have no colours of their own for,
-- worked out from Normal. the heading ramp sits below h1 rather than
-- straddling the body colour: h1 is the only level brighter than the text
-- around it, which is what makes it read as the chapter. h2 takes body
-- brightness and everything after it dims. bold carries "this is a
-- heading" for the top three; brightness carries how deep it is.
-- leap's label is inverse video written as explicit swapped colours rather
-- than `reverse`: leap derives its dimmed-label group by numerically
-- blending LeapLabel with the background, and that needs real values.
local function derived(bg)
  local normal = vim.api.nvim_get_hl(0, { name = "Normal" })
  local fg, ground = normal.fg, normal.bg
  local peak = bg == "dark" and 0xffffff or 0x000000
  return {
    ["@markup.heading.1.markdown"] = { fg = mix(fg, peak, 0.85), bold = true },
    ["@markup.heading.2.markdown"] = { fg = fg, bold = true },
    ["@markup.heading.3.markdown"] = { fg = mix(fg, ground, 0.22), bold = true },
    ["@markup.heading.4.markdown"] = { fg = mix(fg, ground, 0.42) },
    ["@markup.heading.5.markdown"] = { fg = mix(fg, ground, 0.60) },
    ["@markup.heading.6.markdown"] = { fg = mix(fg, ground, 0.78) },
    RenderMarkdownBullet = { link = "Comment" },
    RenderMarkdownDash = { link = "Comment" },
    RenderMarkdownQuote = { link = "Comment" },
    RenderMarkdownCodeInfo = { link = "Comment" },
    LeapLabel = { fg = ground, bg = fg, bold = true, nocombine = true },
    LeapMatch = { underline = true, bold = true },
    LeapBackdrop = { link = "Comment" },
  }
end

local function serialise_sorted(tbl)
  local names = vim.tbl_keys(tbl)
  table.sort(names)
  local lines = {}
  for _, name in ipairs(names) do
    local attrs = vim.inspect(tbl[name], { indent = "", newline = " " })
    lines[#lines + 1] = ("  [%q] = %s,"):format(name, attrs)
  end
  return table.concat(lines, "\n")
end

local function write(path, chunks)
  local f = assert(io.open(path, "w"))
  f:write(table.concat(chunks, "\n"), "\n")
  f:close()
end

local function hex(colour)
  return ("#%06X"):format(colour)
end

function M.compile()
  require("lazy").load({ plugins = { "zenbones.nvim" } })
  vim.g.zenwritten = CONFIG

  -- the plugin's own colors file, explicitly: `colorscheme zenwritten`
  -- would find the compiled file this is about to regenerate
  local source = vim.api.nvim_get_runtime_file("colors/zenwritten.vim", false)[1]
  assert(source, "zenbones' colors/zenwritten.vim not found on the runtimepath")

  local sets = {}
  for _, bg in ipairs({ "dark", "light" }) do
    vim.o.background = bg
    -- the compiled colorscheme starts with `highlight clear` too, so a
    -- group that already has its value then need not be written down.
    -- groups neovim defines itself stay whenever the theme changes them
    vim.cmd("highlight clear")
    local defaults = vim.api.nvim_get_hl(0, {})
    vim.cmd.source(source)
    for name, attrs in pairs(derived(bg)) do
      vim.api.nvim_set_hl(0, name, attrs)
    end
    local hl = {}
    for name, attrs in pairs(vim.api.nvim_get_hl(0, {})) do
      if not vim.deep_equal(attrs, defaults[name]) and (next(defaults[name] or {}) or not absent(name)) then
        hl[name] = attrs
      end
    end
    local terminal = {}
    for i = 0, 15 do
      terminal[i + 1] = vim.g["terminal_color_" .. i]
    end
    -- zenbones' own lualine theme, by path: a plain require would find the
    -- compiled copy in this config, which sits first on the runtimepath, and
    -- regenerate it from its previous output
    local lualine_source
    for _, path in ipairs(vim.api.nvim_get_runtime_file("lua/lualine/themes/zenwritten.lua", true)) do
      if not vim.startswith(vim.fs.normalize(path), vim.fs.normalize(vim.fn.stdpath("config")) .. "/") then
        lualine_source = path
      end
    end
    assert(lualine_source, "zenbones' lualine theme not found on the runtimepath")
    sets[bg] = {
      hl = hl,
      terminal = terminal,
      lualine = dofile(lualine_source),
    }
  end

  local config_dir = vim.fn.stdpath("config")
  local generated = "-- Generated by lua/zenwritten_compile.lua - do not edit by hand;"
    .. "\n-- change the configuration there and recompile instead."

  -- one palette per background, so a startup parses only the one it needs
  for bg, set in pairs(sets) do
    write(config_dir .. "/lua/zenwritten_palette/" .. bg .. ".lua", {
      generated,
      "return {",
      "terminal = " .. vim.inspect(set.terminal, { indent = "", newline = " " }) .. ",",
      "hl = {",
      serialise_sorted(set.hl),
      "},",
      "}",
    })
  end

  write(config_dir .. "/colors/zenwritten.lua", {
    "-- zenwritten, compiled flat: the highlights lush would have built at",
    "-- startup, written down once instead (lua/zenwritten_palette/).",
    generated,
    'vim.cmd("highlight clear")',
    'if vim.fn.exists("syntax_on") == 1 then vim.cmd("syntax reset") end',
    'vim.g.colors_name = "zenwritten"',
    "",
    'local bg = vim.o.background == "light" and "light" or "dark"',
    'local set = require("zenwritten_palette." .. bg)',
    "for name, attrs in pairs(set.hl) do",
    "  vim.api.nvim_set_hl(0, name, attrs)",
    "end",
    "for i, colour in ipairs(set.terminal) do",
    '  vim.g["terminal_color_" .. (i - 1)] = colour',
    "end",
  })

  write(config_dir .. "/lua/lualine/themes/zenwritten.lua", {
    "-- The statusline's colours, for whichever background is current when",
    "-- lualine asks.",
    generated,
    "local themes = {",
    "dark = " .. vim.inspect(sets.dark.lualine, { indent = "  ", newline = "\n" }) .. ",",
    "light = " .. vim.inspect(sets.light.lualine, { indent = "  ", newline = "\n" }) .. ",",
    "}",
    "return vim.deepcopy(themes[vim.o.background] or themes.dark)",
  })

  -- wezterm's two schemes, so the terminal background is the editor's
  -- and the ansi colours are the theme's own. the repo is one tree with
  -- the config junctioned in, so wezterm/ sits beside the real nvim/
  local schemes = {}
  for bg, set in pairs(sets) do
    local fg, ground = hex(set.hl.Normal.fg), hex(set.hl.Normal.bg)
    schemes["zenwritten " .. bg] = {
      background = ground,
      foreground = fg,
      cursor_bg = fg,
      cursor_fg = ground,
      cursor_border = fg,
      selection_bg = set.terminal[9],
      selection_fg = fg,
      split = set.terminal[9],
      ansi = vim.list_slice(set.terminal, 1, 8),
      brights = vim.list_slice(set.terminal, 9, 16),
    }
  end
  local repo = vim.fs.dirname(vim.uv.fs_realpath(config_dir) or config_dir)
  write(repo .. "/wezterm/zenwritten.lua", {
    "-- Generated by nvim/lua/zenwritten_compile.lua - do not edit by hand;",
    "-- change the configuration there and recompile instead.",
    "return " .. vim.inspect(schemes),
  })

  vim.notify("compiled zenwritten into colors/, lua/lualine/themes/ and wezterm/")
end

return M
