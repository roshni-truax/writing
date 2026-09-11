# writing

the editor for writing prose: a neovim config, a wezterm config, printer,
which turns a markdown file into a pdf, and viewer, a pdf viewer that runs
in the terminal. printer sets a manuscript as an a5 page, and a deck - one
whose frontmatter says `slides: true` - through `printer/slides`, drawn in
characters (`printer/slides/example.md` shows the whole of what it reads).
the words themselves live on the nas share, not here.

```powershell
.\install.ps1
```

that junctions neovim and wezterm at this folder and puts `printer` and `viewer` on the path,
so this checkout is the live config. re-run it if the folder moves. the
junctions need a local folder, so this repo is cloned to `~\.config\writing` on
each machine; the organization monorepo carries it as a submodule.

it expects, all from winget: neovim, wezterm, `JetBrainsMono Nerd Font`,
pandoc and typst for the pdf export, `Automattic.harper-ls` for proofreading,
lazygit, and python with `pypdfium2` and `pillow` for viewer.

the same setup runs on the nas, over ssh from the same terminal, minus
wezterm: `system/scripts/setup-nas.sh` in the monorepo installs the tools
and links the config there.

the theme is compiled from zenbones: after changing `nvim/lua/zenwritten_compile.lua`,
run `:lua require("zenwritten_compile").compile()` and commit the generated
files in `nvim/colors`, `nvim/lua/zenwritten_palette`, `nvim/lua/lualine/themes`,
`wezterm/` and `palette/`.

`palette/zenwritten.json` is the theme as plain data, for the programs here
that read neither lua nor a colorscheme: printer sets a deck in it and viewer
tints its status line with it.
