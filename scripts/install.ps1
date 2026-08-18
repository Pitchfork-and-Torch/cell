# Install cell CLI shim + optional Grok MCP stanza.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Bin = Join-Path $env:USERPROFILE ".grok\bin"
$Shim = Join-Path $Bin "cell.cmd"
$Entry = Join-Path $Root "scripts\cell.py"
$McpEntry = Join-Path $Root "scripts\mcp_entry.py"
$Config = Join-Path $env:USERPROFILE ".grok\config.toml"

New-Item -ItemType Directory -Force -Path $Bin | Out-Null
$shimBody = @"
@echo off
py -3 "$Entry" %*
"@
Set-Content -Path $Shim -Value $shimBody -Encoding ascii
Write-Host "wrote $Shim"

try {
    py -3 -m pip install -e $Root --quiet
    Write-Host "pip install -e ok"
} catch {
    Write-Host "pip install -e skipped or failed (shim still works): $_"
}

if (Test-Path $Config) {
    $toml = Get-Content -Raw -Path $Config
    if ($toml -notmatch '\[mcp_servers\.cell\]') {
        $block = @"

[mcp_servers.cell]
command = "py"
args = [
    "-3",
    "$($McpEntry -replace '\\','/')",
]
enabled = true
startup_timeout_sec = 20
"@
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::AppendAllText($Config, $block, $utf8)
        Write-Host "appended [mcp_servers.cell] to config.toml"
    } else {
        Write-Host "mcp_servers.cell already present"
    }
}

Write-Host ""
Write-Host "next:"
Write-Host "  cell init --import-env PATH\\to\\.env"
Write-Host "  cell doctor"
Write-Host "  Restart Grok Build to load the cell MCP tools."
