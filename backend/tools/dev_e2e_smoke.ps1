<#
  Local smoke: migrations -> seed -> inbound POST -> batch_processor run_once -> (optional) outbox run_once

  Prerequisites (same shell or system env):
    $env:DATABASE_URL = postgresql+psycopg://USER:PASS@localhost:5432/zysmart
    $env:PYTHONPATH   = repo root (this script sets it from location)

  Gateway on :8081 and AI engine on :8083 must be running (unless you only test inbound).

  Usage:
    cd <repo-root>
    .\backend\tools\dev_e2e_smoke.ps1 -CustomerPhoneE164 "+9198xxxxxxx"

  Optional:
    -MetaPhoneNumberId "1098044196727032"
    -SkipOutbox        # if META_ACCESS_TOKEN not set yet
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $CustomerPhoneE164,

    [string] $MetaPhoneNumberId = "1098044196727032",

    [switch] $SkipOutbox
)

$ErrorActionPreference = 'Stop'

$toolsDir = $PSScriptRoot
$backendDir = Split-Path $toolsDir -Parent
$repoRoot = (Resolve-Path (Split-Path $backendDir -Parent)).Path
Set-Location $repoRoot
$env:PYTHONPATH = $repoRoot

if (-not $env:DATABASE_URL) {
    Write-Error 'Set DATABASE_URL first (postgresql+psycopg://.../zysmart).'
}

$py = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    Write-Error "Missing venv python at: $py"
}

function Invoke-Py {
    param([string[]] $PyArgs)
    & $py @PyArgs
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $py $($PyArgs -join ' ')" }
}

Write-Host '==> alembic upgrade head' -ForegroundColor Cyan
Invoke-Py @('-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head')

Write-Host '==> dev_seed' -ForegroundColor Cyan
Invoke-Py @('backend/tools/dev_seed.py', '--meta-phone-number-id', $MetaPhoneNumberId)

try {
    $h = Invoke-WebRequest -Uri 'http://127.0.0.1:8081/health' -UseBasicParsing -TimeoutSec 3
    if ($h.StatusCode -ne 200) { throw 'health not 200' }
}
catch {
    $gatewayHint = @(
        'WA gateway is not reachable on http://127.0.0.1:8081/health .',
        'Start another terminal from repo root (venv + PYTHONPATH + DATABASE_URL), then run:',
        '  .\.venv\Scripts\python.exe -m uvicorn backend.apps.wa_gateway.main:app --reload --port 8081'
    ) -join [Environment]::NewLine
    Write-Error $gatewayHint
}

Write-Host '==> dev_send_inbound (customer = your number)' -ForegroundColor Cyan
$smokeText = 'ZY dev_e2e_smoke ' + (Get-Date -Format o)
Invoke-Py @(
    'backend/tools/dev_send_inbound.py',
    '--meta-phone-number-id', $MetaPhoneNumberId,
    '--from', $CustomerPhoneE164,
    '--text', $smokeText
)

if (-not $env:AI_ENGINE_URL) {
    $env:AI_ENGINE_URL = 'http://127.0.0.1:8083'
    Write-Host "Set AI_ENGINE_URL default to $($env:AI_ENGINE_URL)" -ForegroundColor Yellow
}

try {
    $ai = Invoke-WebRequest -Uri 'http://127.0.0.1:8083/health' -UseBasicParsing -TimeoutSec 2
    if ($ai.StatusCode -ne 200) { throw 'bad' }
    Write-Host 'AI engine health: OK' -ForegroundColor Green
}
catch {
    Write-Host 'WARN: AI engine not reachable on http://127.0.0.1:8083/health — batch will HANDOFF without REPLY.' -ForegroundColor Yellow
    Write-Host 'Start: .\.venv\Scripts\python.exe -m uvicorn backend.apps.ai_engine.main:app --reload --port 8083' -ForegroundColor Yellow
}

Write-Host '==> debounce wait + batch retries + outbox (pipeline tail)' -ForegroundColor Cyan
if ($SkipOutbox) {
    Invoke-Py @('backend/tools/dev_run_pipeline_tail.py', '--skip-outbox')
}
else {
    Invoke-Py @('backend/tools/dev_run_pipeline_tail.py')
}

Write-Host '==> dev_check' -ForegroundColor Cyan
Invoke-Py @('backend/tools/dev_check.py')

Write-Host ''
Write-Host 'Done. Check your phone for WhatsApp. If outbox FAILED/DEAD, see wa_outbox.last_error_detail (dev_check).' -ForegroundColor Green
