" Markdown is highlighted by treesitter - neovim's own ftplugin starts it.
" The stock regex syntax would still load on top, dragging the html and css
" syntaxes in with it: roughly 80ms per file spent repeating work treesitter
" has already done. This stub sits earlier on the runtimepath and claims the
" syntax as loaded, so the stock chain bows out at its own guard clause.
let b:current_syntax = "markdown"
