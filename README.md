# writing

the editor for writing prose: a neovim config, a wezterm config, and tpv, a
pdf viewer that runs in the terminal. the words themselves live on the nas
share, not here.

```powershell
.\install.ps1
```

that junctions neovim and wezterm at this folder and puts `tpv` on the path,
so this checkout is the live config. re-run it if the folder moves. the
junctions need a local folder, so this repo is cloned to `~\.config\writing` on
each machine; the organization monorepo carries it as a submodule.

it expects, all from winget: neovim, wezterm, `JetBrainsMono Nerd Font`,
pandoc and typst for the pdf export, `Automattic.harper-ls` for proofreading,
lazygit, and python with `pypdfium2` and `pillow` for tpv.

the theme is compiled from zenbones: after changing `nvim/lua/zenwritten_compile.lua`,
run `:lua require("zenwritten_compile").compile()` and commit the generated
files in `nvim/colors`, `nvim/lua/zenwritten_palette`, `nvim/lua/lualine/themes`
and `wezterm/`.
