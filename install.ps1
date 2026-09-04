<#
    Points Neovim and WezTerm at this folder.

    Both programs look for their config in a fixed place. Rather than keep a
    copy in each, this makes that place a junction back to here, so the repo is
    the live config and there is only ever one version of a file.

    Junctions, unlike symlinks, need no administrator rights.

    Run from inside the repo:  .\install.ps1
#>

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot

$links = @(
    @{ Name = 'neovim';  Link = Join-Path $env:LOCALAPPDATA 'nvim';        Target = Join-Path $repo 'nvim' }
    @{ Name = 'wezterm'; Link = Join-Path $HOME '.config\wezterm';         Target = Join-Path $repo 'wezterm' }
)

foreach ($l in $links) {
    $link = $l.Link
    $target = $l.Target

    if (-not (Test-Path -LiteralPath $target)) {
        throw "missing in the repo: $target"
    }

    if (Test-Path -LiteralPath $link) {
        $item = Get-Item -LiteralPath $link -Force
        if ($item.LinkType -eq 'Junction') {
            # Delete the link itself. Remove-Item -Recurse would follow it and
            # delete what it points at, which here is the repo.
            [System.IO.Directory]::Delete($link, $false)
            Write-Host "  replaced the existing junction for $($l.Name)"
        }
        else {
            $backup = "$link.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
            Move-Item -LiteralPath $link -Destination $backup
            Write-Host "  moved the existing $($l.Name) config aside -> $backup"
        }
    }

    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    Write-Host "  $($l.Name): $link -> $target"
}

# tpv, the pdf viewer, as a command. WindowsApps is on every user's PATH
# already, so a two-line shim there pointing back into the repo makes
# `tpv file.pdf` work in any shell, with the repo staying the only copy.
$shim = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\tpv.cmd'
Set-Content -LiteralPath $shim -Encoding ascii -Value @(
    '@echo off'
    "python `"$(Join-Path $repo 'tpv\tpv.py')`" %*"
)
Write-Host "  tpv: $shim -> $(Join-Path $repo 'tpv\tpv.py')"

# WezTerm reads ~\.wezterm.lua in preference to ~\.config\wezterm, so a
# leftover there would silently win over the repo.
$stray = Join-Path $HOME '.wezterm.lua'
if (Test-Path -LiteralPath $stray) {
    $backup = "$stray.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
    Move-Item -LiteralPath $stray -Destination $backup
    Write-Host "  moved ~\.wezterm.lua aside -> $backup (it would have taken precedence)"
}

Write-Host ''
Write-Host 'done. open a new wezterm window; neovim installs its plugins on first start.'
Write-Host 'the jetbrains mono nerd font is not installed by this script - see README.md.'
