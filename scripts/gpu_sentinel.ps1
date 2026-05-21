# Chat Y: GPU VRAM sentinel wrapper (calls Python CLI).
#
#   cd C:\Users\TV_Station\.cursor\projects\empty-window
#   . .\dev-env.ps1
#   .\scripts\gpu_sentinel.ps1 status
#   .\scripts\gpu_sentinel.ps1 busy -Owner "wsl:owner-lora" -Note "llama.cpp 8082"
#   .\scripts\gpu_sentinel.ps1 available

param(
    [Parameter(Position = 0)]
    [ValidateSet('status', 'available', 'busy', 'offline')]
    [string]$Action = 'status',
    [string]$Owner,
    [string]$Note,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if (Test-Path (Join-Path $root 'dev-env.ps1')) {
    . (Join-Path $root 'dev-env.ps1')
}

$map = @{
    status    = @('status')
    available = @('set-available')
    busy      = @('set-busy')
    offline   = @('set-offline')
}
$argsList = @()
$argsList += $map[$Action]
if ($Owner) { $argsList += @('--owner', $Owner) }
if ($Note) { $argsList += @('--note', $Note) }
if ($Force) { $argsList += '--force' }

python (Join-Path $root 'backend\tools\gpu_sentinel_cli.py') @argsList
exit $LASTEXITCODE
