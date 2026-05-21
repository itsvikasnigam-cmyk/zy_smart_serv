# Shared paths for project-local Ollama (dot-sourced by scripts/*.ps1).

function Get-ZyRepoRoot {
    if ($env:ZY_BASE_DIR -and (Test-Path $env:ZY_BASE_DIR)) {
        return (Resolve-Path $env:ZY_BASE_DIR).Path
    }
    return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Get-OllamaLocalPaths {
    $root = Get-ZyRepoRoot
    $vendor = Join-Path $root 'vendor\ollama'
    [PSCustomObject]@{
        Root   = $root
        Vendor = $vendor
        Exe    = Join-Path $vendor 'ollama.exe'
        Models = Join-Path $root 'models\ollama'
        Host   = '127.0.0.1:11435'
        ApiUrl = 'http://127.0.0.1:11435'
    }
}

function Set-OllamaLocalEnv {
    param($Paths)
    $env:OLLAMA_HOST = $Paths.Host
    $env:OLLAMA_MODELS = $Paths.Models
    $env:LOCALAPPDATA = Join-Path $Paths.Vendor 'runtime'
    New-Item -ItemType Directory -Force -Path $env:OLLAMA_MODELS | Out-Null
    New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA | Out-Null
}

function Test-OllamaLocalApi {
    param([string]$ApiUrl = 'http://127.0.0.1:11435')
    try {
        $null = Invoke-RestMethod -Uri "$ApiUrl/api/tags" -TimeoutSec 3
        return $true
    }
    catch {
        return $false
    }
}

function Wait-OllamaLocalApi {
    param(
        [string]$ApiUrl = 'http://127.0.0.1:11435',
        [int]$Seconds = 45
    )
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-OllamaLocalApi -ApiUrl $ApiUrl) {
            return $true
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Start-OllamaLocalServerWindow {
    $startScript = Join-Path $PSScriptRoot 'start_ollama_local.ps1'
    if (-not (Test-Path $startScript)) {
        throw "Missing $startScript"
    }
    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoExit',
        '-ExecutionPolicy', 'Bypass',
        '-File', "`"$startScript`""
    ) | Out-Null
}
