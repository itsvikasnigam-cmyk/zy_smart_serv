# Dot-source from repo root before python backend tools/workers:
#   cd C:\Users\TV_Station\.cursor\projects\empty-window; . .\dev-env.ps1
#
# Loads .env (repo root first, else backend\.env) + sets PYTHONPATH.

$root = $PSScriptRoot
if (-not $root) {
    $root = (Get-Location).Path
}

Set-Location $root
$env:PYTHONPATH = $root

function Import-DotEnvFile {
    param(
        [string]$Path,
        [switch]$OnlyIfUnset
    )
    if (-not (Test-Path $Path)) {
        return $false
    }
    $loadedAny = $false
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq '' -or $line.StartsWith('#')) {
            return
        }
        $eq = $line.IndexOf('=')
        if ($eq -lt 1) {
            return
        }
        $name = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1).Trim()
        if ($val.StartsWith('"') -and $val.EndsWith('"')) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        if ($val.StartsWith("'") -and $val.EndsWith("'")) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        if (-not $name) {
            return
        }
        if ($OnlyIfUnset -and (Test-Path "env:$name")) {
            $existing = (Get-Item "env:$name").Value
            if ($null -ne $existing -and "$existing".Trim() -ne '') {
                return
            }
        }
        Set-Item -Path "env:$name" -Value $val
        $loadedAny = $true
    }
    return $loadedAny
}

$rootEnv = Join-Path $root '.env'
$backendEnv = Join-Path $root 'backend\.env'
$loadedRoot = Import-DotEnvFile $rootEnv
if ($loadedRoot) {
    Write-Host 'Loaded: .env (repo root)'
}
if (Import-DotEnvFile $backendEnv -OnlyIfUnset) {
    if ($loadedRoot) {
        Write-Host 'Merged: backend\.env (fills unset vars only)'
    }
    else {
        Write-Host 'Loaded: backend\.env (no root .env - OK for dev)'
    }
}
elseif (-not $loadedRoot) {
    Write-Host 'No .env found - using defaults below'
}

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = 'postgresql+psycopg://postgres:Vikas%401983@localhost:5432/zysmart'
}
if (-not $env:CLIENT_API_JWT_SECRET) {
    $env:CLIENT_API_JWT_SECRET = 'dev-insecure-change-me'
}
if (-not $env:APP_ENV) {
    $env:APP_ENV = 'dev'
}

# Option C: active code/data root (now = this repo on C:). Later prod on D: set ZY_BASE_DIR in backend\.env.
if (-not $env:ZY_BASE_DIR) {
    $env:ZY_BASE_DIR = $root
}

Write-Host "PYTHONPATH=$env:PYTHONPATH"
Write-Host "DATABASE_URL=$env:DATABASE_URL"
Write-Host "ZY_BASE_DIR=$env:ZY_BASE_DIR"

$localOllama = Join-Path $env:ZY_BASE_DIR 'vendor\ollama\ollama.exe'
if (Test-Path $localOllama) {
    Write-Host "Local Ollama: $localOllama (API :11435 - run .\scripts\start_ollama_local.ps1)"
}
