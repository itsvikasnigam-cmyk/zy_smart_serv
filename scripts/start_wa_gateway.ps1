# Stop anything on 8081 and start wa_gateway from THIS repo.
# Usage:
#   cd C:\Users\TV_Station\.cursor\projects\empty-window
#   .\scripts\start_wa_gateway.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. (Join-Path $root "dev-env.ps1")

Write-Host "=== Code on disk (this repo) ==="
python -c "import backend.apps.wa_gateway.main as m; print('  file:', m.__file__); print('  build:', m.GATEWAY_BUILD_ID); print('  health:', m.health())"

Write-Host "`nStopping listeners on port 8081..."
& (Join-Path $root "scripts\kill_port_8081.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Starting wa_gateway on http://127.0.0.1:8081 (no --reload, single process) ..."
Write-Host "Look for: WA Gateway build=gate1-2026-05-15"
python -m uvicorn backend.apps.wa_gateway.main:app --host 127.0.0.1 --port 8081
