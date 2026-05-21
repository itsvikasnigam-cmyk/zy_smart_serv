# Chat Z: rollback hook — marks release rolled_back and disables canary.
#
#   .\scripts\rollback_release.ps1 -BuildId dev-20260522 -Note "misfire rollback"

param(
    [Parameter(Mandatory = $true)]
    [string]$BuildId,
    [string]$Note = "PowerShell rollback hook"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if (Test-Path (Join-Path $root 'dev-env.ps1')) {
    . (Join-Path $root 'dev-env.ps1')
}

$pyArgs = @(
    (Join-Path $root 'backend\tools\rollback_ops_release.py'),
    '--build-id', $BuildId,
    '--note', $Note
)
python @pyArgs
exit $LASTEXITCODE
