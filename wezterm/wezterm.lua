-- WezTerm, matched to the Neovim setup.
--
-- The colour schemes are zenwritten's own palettes, written to zenwritten.lua
-- beside this file by nvim/lua/zenwritten_compile.lua, so the terminal
-- background and the editor background are the same colour and there is no
-- seam where one ends.
--
-- Multiplexing is WezTerm's own, driven from a leader key the way tmux is, so
-- there is no second program to install or configure.

local wezterm = require("wezterm")
local act = wezterm.action
local config = wezterm.config_builder()

-- Neovim spends ~65ms of every startup asking Windows to resolve a locale
-- and then hunting for message catalogues it will never use (measured with
-- --startuptime: "locale set"). Pinning LANG short-circuits the search,
-- and the C locale's untranslated messages are the English ones anyway.
config.set_environment_variables = { LANG = "C" }

-- ---------------------------------------------------------------- colours --

config.color_schemes = require("zenwritten")

-- Follows whatever Windows is set to, so the terminal and Neovim agree without
-- either being told twice. <leader>b flips Neovim on its own if you want them
-- to differ for a moment.
config.color_scheme = wezterm.gui.get_appearance():find("Dark") and "zenwritten dark"
  or "zenwritten light"

-- Neovim cannot ask the terminal what colour it is. The query for it (OSC 11)
-- is dropped by Windows' console layer: a bare `nvim -u NONE` in a light
-- window still comes up dark. So WezTerm writes its current appearance down
-- here and Neovim reads the file on startup - see nvim/lua/appearance.lua.
--
-- The file is machine-local state, deliberately outside this repo.
local STATE_PATH = (os.getenv("LOCALAPPDATA") or os.getenv("TMPDIR") or "/tmp")
  .. "/wezterm-appearance"

local function record_appearance(scheme)
  local file = io.open(STATE_PATH, "w")
  if file then
    file:write(scheme:find("light") and "light" or "dark", "\n")
    file:close()
  end
end

-- Fires for each window as it opens and whenever the config reloads, which
-- includes the reload that applying an override triggers. Deliberately keyed
-- to a window: `wezterm cli` calls evaluate this file too, and without a
-- window to ask they would write a guess over the real answer.
wezterm.on("window-config-reloaded", function(window)
  record_appearance(window:effective_config().color_scheme)
end)

-- Alt+b flips the terminal, mirroring <leader>b in Neovim. The override applies
-- to the focused window and lasts until it closes; a new window starts from the
-- system appearance again.
wezterm.on("toggle-theme", function(window)
  local overrides = window:get_config_overrides() or {}
  local current = overrides.color_scheme or config.color_scheme
  local next_scheme = current == "zenwritten dark" and "zenwritten light"
    or "zenwritten dark"
  overrides.color_scheme = next_scheme
  window:set_config_overrides(overrides)
  record_appearance(next_scheme)
end)

-- ------------------------------------------------------------------- type --

-- JetBrains Mono, chosen for its weight range: it goes to ExtraBold (800),
-- which is what lets a heading read as a heading without a single `#`, icon
-- or colour. The two ends are what matter: the body weight, and anything
-- Neovim marks bold drawn ExtraBold. Change either word to taste.
local FAMILY = "JetBrainsMono Nerd Font Mono"
local BODY = "Regular"      -- "Light" for a wider gap to the heading weight
local HEAVY = "ExtraBold"   -- "Bold" for a gentler difference

config.font = wezterm.font({ family = FAMILY, weight = BODY })

-- Bold uses a real heavy face rather than a synthesised one, and bold italic
-- keeps the matching weight so emphasis does not jump around mid-sentence.
config.font_rules = {
  {
    intensity = "Bold",
    italic = false,
    font = wezterm.font({ family = FAMILY, weight = HEAVY }),
  },
  {
    intensity = "Bold",
    italic = true,
    font = wezterm.font({ family = FAMILY, weight = HEAVY, style = "Italic" }),
  },
}
config.font_size = 13.0
config.line_height = 1.15   -- a little air between lines, for reading prose
config.freetype_load_target = "Light"
config.freetype_render_target = "HorizontalLcd"

-- ----------------------------------------------------------------- window --

config.window_padding = { left = 28, right = 28, top = 20, bottom = 16 }
config.window_decorations = "RESIZE"
config.initial_cols = 110
config.initial_rows = 34
config.scrollback_lines = 10000
config.audible_bell = "Disabled"
config.window_close_confirmation = "NeverPrompt"
config.adjust_window_size_when_changing_font_size = false
config.default_cursor_style = "SteadyBar"

-- The tab bar only appears once there is more than one tab, so a single
-- writing window is nothing but text.
config.hide_tab_bar_if_only_one_tab = true
config.use_fancy_tab_bar = false
config.tab_bar_at_bottom = true
config.tab_max_width = 24

-- ----------------------------------------------------------- multiplexing --

-- One chord, no leader. Alt is the only modifier left that is genuinely free
-- here: WezTerm's own Alt bindings are Alt+Enter and three that apply only
-- inside copy mode, and PSReadLine claims just Alt+d and the digit arguments.
--
-- Ctrl is deliberately left alone. Neovim uses Ctrl+h/j/k/l to move between its
-- own splits, so Ctrl stays inside the editor and Alt moves between WezTerm
-- panes. Nothing is ambiguous and nothing has to be pressed twice.
--
-- Dropping the leader also hands Ctrl+a back to the shell, where it is
-- beginning-of-line.
config.keys = {
  -- panes: move
  { key = "h", mods = "ALT", action = act.ActivatePaneDirection("Left") },
  { key = "j", mods = "ALT", action = act.ActivatePaneDirection("Down") },
  { key = "k", mods = "ALT", action = act.ActivatePaneDirection("Up") },
  { key = "l", mods = "ALT", action = act.ActivatePaneDirection("Right") },

  -- panes: make and unmake. s and v echo vim's own :sp and :vs.
  { key = "s", mods = "ALT", action = act.SplitVertical({ domain = "CurrentPaneDomain" }) },
  { key = "v", mods = "ALT", action = act.SplitHorizontal({ domain = "CurrentPaneDomain" }) },
  { key = "z", mods = "ALT", action = act.TogglePaneZoomState },
  { key = "x", mods = "ALT", action = act.CloseCurrentPane({ confirm = true }) },

  -- panes: resize on the arrows, pairing with ctrl+arrows inside
  -- neovim. Neovim cannot use shifted letters - the console layer folds
  -- ctrl+shift+h into ctrl+h before it arrives - so arrows are the shape
  -- the mirror takes on both sides.
  { key = "LeftArrow", mods = "ALT", action = act.AdjustPaneSize({ "Left", 3 }) },
  { key = "DownArrow", mods = "ALT", action = act.AdjustPaneSize({ "Down", 3 }) },
  { key = "UpArrow", mods = "ALT", action = act.AdjustPaneSize({ "Up", 3 }) },
  { key = "RightArrow", mods = "ALT", action = act.AdjustPaneSize({ "Right", 3 }) },

  -- tabs
  { key = "t", mods = "ALT", action = act.SpawnTab("CurrentPaneDomain") },
  { key = "[", mods = "ALT", action = act.ActivateTabRelative(-1) },
  { key = "]", mods = "ALT", action = act.ActivateTabRelative(1) },
  { key = "w", mods = "ALT", action = act.CloseCurrentTab({ confirm = true }) },

  -- light / dark, the same letter Neovim uses
  { key = "b", mods = "ALT", action = act.EmitEvent("toggle-theme") },

  -- font size, without the window jumping about. On alt rather than ctrl:
  -- ctrl+- and ctrl-+ belong to the viewer (fit width, fit page), and a binding
  -- here would fire alongside it - the terminal cannot yield a bound key
  -- to one program and keep it from another.
  { key = "=", mods = "ALT", action = act.IncreaseFontSize },
  { key = "-", mods = "ALT", action = act.DecreaseFontSize },
  { key = "0", mods = "ALT", action = act.ResetFontSize },
}

return config
