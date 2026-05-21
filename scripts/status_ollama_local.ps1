# Quick check: project-local Ollama. Works from any folder.

$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot '_ollama_local_common.ps1')
$p = Get-OllamaLocalPaths

Write-Host "Repo root:   $($p.Root)"
Write-Host "Binary:      $(if (Test-Path $p.Exe) { $p.Exe } else { 'MISSING - run setup_ollama_local.ps1' })"
Write-Host "Models dir:  $($p.Models)"
if (Test-Path $p.Models) {
    $sum = (Get-ChildItem $p.Models -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sum) { $sum = 0 }
    Write-Host ("Model data:  {0:N2} GB" -f ($sum / 1GB))
}
if (Test-OllamaLocalApi -ApiUrl $p.ApiUrl) {
    Write-Host 'API :11435:  UP'
    try {
        $r = Invoke-RestMethod -Uri "$($p.ApiUrl)/api/tags" -TimeoutSec 5
        if ($r.models) {
            $r.models | ForEach-Object { Write-Host ('  - ' + $_.name) }
        }
    }
    catch {
        Write-Host '  (could not list models)'
    }
}
else {
    Write-Host 'API :11435:  DOWN'
    Write-Host "Start: & '$((Join-Path $PSScriptRoot 'start_ollama_local.ps1'))'"
}
