# Start project-local Ollama on port 11435. Run from ANY folder.
#
#   cd C:\Users\TV_Station\.cursor\projects\empty-window; . .\dev-env.ps1
#   & "C:\Users\TV_Station\.cursor\projects\empty-window\scripts\start_ollama_local.ps1"
#
# Leave this window open.

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_ollama_local_common.ps1')
$p = Get-OllamaLocalPaths

if (-not (Test-Path $p.Exe)) {
    Write-Host "Missing $($p.Exe)"
    Write-Host "From repo root run: .\scripts\setup_ollama_local.ps1"
    exit 1
}

Set-OllamaLocalEnv -Paths $p

Write-Host "Repo root:   $($p.Root)"
Write-Host "OLLAMA_HOST: $($p.Host)"
Write-Host "OLLAMA_MODELS: $($p.Models)"
Write-Host "Starting: $($p.Exe) serve"
Write-Host '(Ctrl+C to stop - keep this window open while pulling models)'
Write-Host ''

Set-Location $p.Vendor
& $p.Exe serve
