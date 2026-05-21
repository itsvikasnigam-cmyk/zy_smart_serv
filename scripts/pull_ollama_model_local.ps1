# Pull a model into project-local Ollama. Run from repo root (or any folder).
#
#   cd C:\Users\TV_Station\.cursor\projects\empty-window; . .\dev-env.ps1
#   .\scripts\pull_ollama_model_local.ps1
#   .\scripts\pull_ollama_model_local.ps1 -AutoStart

param(
    [string]$Model = 'llama3.2',
    [switch]$AutoStart
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_ollama_local_common.ps1')
$p = Get-OllamaLocalPaths

if (-not (Test-Path $p.Exe)) {
    Write-Host "Missing $($p.Exe) - run from repo root:"
    Write-Host "  cd $($p.Root)"
    Write-Host "  .\scripts\setup_ollama_local.ps1"
    exit 1
}

Set-OllamaLocalEnv -Paths $p

if (-not (Test-OllamaLocalApi -ApiUrl $p.ApiUrl)) {
    if ($AutoStart) {
        Write-Host 'API :11435 is down - opening start_ollama_local.ps1 in a new window...'
        Start-OllamaLocalServerWindow
        Write-Host 'Waiting for server (up to 45s)...'
        if (-not (Wait-OllamaLocalApi -ApiUrl $p.ApiUrl)) {
            Write-Host 'ERROR: server did not become ready. Check the new PowerShell window for errors.'
            exit 1
        }
    }
    else {
        Write-Host 'ERROR: project Ollama is not running on http://127.0.0.1:11435'
        Write-Host ''
        Write-Host 'Step A - open a NEW terminal, leave it open:'
        Write-Host "  cd $($p.Root)"
        Write-Host '  . .\dev-env.ps1'
        Write-Host "  & '$((Join-Path $PSScriptRoot 'start_ollama_local.ps1'))'"
        Write-Host ''
        Write-Host 'Step B - then run pull again, OR use -AutoStart:'
        Write-Host "  .\scripts\pull_ollama_model_local.ps1 -AutoStart"
        exit 1
    }
}

Write-Host "Pulling $Model into $($p.Models) ..."
Push-Location $p.Vendor
try {
    & $p.Exe pull $Model
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($code -ne 0) {
    Write-Host "Pull failed (exit $code). Check the start_ollama_local window for errors."
    exit $code
}
Write-Host "OK: $Model ready (AI_LLM_PRIMARY_MODEL=$Model)"
