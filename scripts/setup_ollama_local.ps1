# Bootstrap project-local Ollama under ZY_BASE_DIR (portable when you move to D:).
#
# Usage (repo root):
#   cd C:\Users\TV_Station\.cursor\projects\empty-window; . .\dev-env.ps1
#   .\scripts\setup_ollama_local.ps1
#
# Copies binaries from your existing Windows install (fast). Optional:
#   .\scripts\setup_ollama_local.ps1 -MigrateModels
#   .\scripts\setup_ollama_local.ps1 -Download   # ~2GB from GitHub (slow)

param(
    [switch]$MigrateModels,
    [switch]$Download,
    [string]$ReleaseTag = 'v0.23.4'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_ollama_local_common.ps1')
$p = Get-OllamaLocalPaths
$root = $p.Root
$vendor = $p.Vendor
$models = $p.Models
$exe = $p.Exe

New-Item -ItemType Directory -Force -Path $vendor | Out-Null
New-Item -ItemType Directory -Force -Path $models | Out-Null

function Copy-OllamaFromSystem {
    $src = Join-Path $env:LOCALAPPDATA 'Programs\Ollama'
    if (-not (Test-Path (Join-Path $src 'ollama.exe'))) {
        throw "System Ollama not found at $src - install from https://ollama.com or use -Download"
    }
    Write-Host "Copying binaries from $src -> $vendor"
    robocopy $src $vendor /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed (exit $LASTEXITCODE)"
    }
}

function Download-OllamaZip {
    $zipUrl = "https://github.com/ollama/ollama/releases/download/$ReleaseTag/ollama-windows-amd64.zip"
    $zipPath = Join-Path $env:TEMP "ollama-windows-amd64-$ReleaseTag.zip"
    Write-Host "Downloading $zipUrl (large, may take several minutes)..."
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
    $extract = Join-Path $env:TEMP "ollama-extract-$ReleaseTag"
    if (Test-Path $extract) {
        Remove-Item -Recurse -Force $extract
    }
    Expand-Archive -Path $zipPath -DestinationPath $extract -Force
    $inner = Get-ChildItem -Path $extract -Recurse -Filter 'ollama.exe' | Select-Object -First 1
    if (-not $inner) {
        throw "ollama.exe not found inside zip"
    }
    $srcDir = $inner.Directory.FullName
    Write-Host "Extracting $srcDir -> $vendor"
    robocopy $srcDir $vendor /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
}

if (Test-Path $exe) {
    Write-Host "Already present: $exe"
}
elseif ($Download) {
    Download-OllamaZip
}
else {
    Copy-OllamaFromSystem
}

if (-not (Test-Path $exe)) {
    throw "Setup failed: missing $exe"
}

if ($MigrateModels) {
    $userModels = Join-Path $env:USERPROFILE '.ollama\models'
    if (Test-Path $userModels) {
        Write-Host "Copying models $userModels -> $models (may be large)..."
        robocopy $userModels $models /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    }
    else {
        Write-Host "No user models at $userModels - skip or run pull_ollama_model_local.ps1"
    }
}

@(
    "ZY_BASE_DIR=$root"
    "OLLAMA_HOST=127.0.0.1:11435"
    "OLLAMA_MODELS=$models"
    "AI_LLM_BASE_URL=http://127.0.0.1:11435/v1"
) | Set-Content -Path (Join-Path $vendor 'zy-ollama-paths.txt') -Encoding utf8

Write-Host ''
Write-Host 'OK: project-local Ollama ready.'
Write-Host "  Binary:  $exe"
Write-Host "  Models:  $models"
Write-Host '  API:     http://127.0.0.1:11435  (separate from system Ollama on :11434)'
Write-Host ''
Write-Host 'Next (always from repo root):'
Write-Host "  cd $root"
Write-Host '  . .\dev-env.ps1'
Write-Host "  & '$((Join-Path $PSScriptRoot 'start_ollama_local.ps1'))'"
Write-Host '  .\scripts\pull_ollama_model_local.ps1 -AutoStart'
Write-Host '  Update backend\.env AI_LLM_BASE_URL=http://127.0.0.1:11435/v1 then restart 8083'
