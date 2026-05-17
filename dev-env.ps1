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
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return $false
    }
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
        if ($name) {
            Set-Item -Path "env:$name" -Value $val
        }
    }
    return $true
}

$rootEnv = Join-Path $root '.env'
$backendEnv = Join-Path $root 'backend\.env'
if (Import-DotEnvFile $rootEnv) {
    Write-Host 'Loaded: .env (repo root)'
}
elseif (Import-DotEnvFile $backendEnv) {
    Write-Host 'Loaded: backend\.env (no root .env - OK for dev)'
}
else {
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

Write-Host "PYTHONPATH=$env:PYTHONPATH"
Write-Host "DATABASE_URL=$env:DATABASE_URL"
