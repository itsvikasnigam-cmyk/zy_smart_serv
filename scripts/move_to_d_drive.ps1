# Option C — future: copy repo to D: and print next steps (does NOT run automatically).
# Usage (when ready):
#   .\scripts\move_to_d_drive.ps1 -TargetRoot D:\zy-smart-ai

param(
    [string]$TargetRoot = "D:\zy-smart-ai"
)

$ErrorActionPreference = "Stop"
$source = $PSScriptRoot | Split-Path -Parent
$TargetRoot = $TargetRoot.TrimEnd('\')

Write-Host "Source (current dev): $source"
Write-Host "Target (production):  $TargetRoot"
Write-Host ""
Write-Host "This script only COPIES files. You must still:"
Write-Host "  1. Install Postgres / point DATABASE_URL at D: data if needed"
Write-Host "  2. Set ZY_BASE_DIR=$TargetRoot in $TargetRoot\backend\.env"
Write-Host "  3. cd $TargetRoot; . .\dev-env.ps1"
Write-Host "  4. python -m alembic -c backend\alembic.ini upgrade head"
Write-Host "  5. Re-create shortcuts / Task Scheduler for workers"
Write-Host "  6. Project Ollama: vendor\ollama + models\ollama copy with the tree - run start_ollama_local.ps1 on D:"
Write-Host ""
$confirm = Read-Host "Copy now? (y/N)"
if ($confirm -ne 'y') {
    Write-Host "Cancelled."
    exit 0
}

New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
robocopy $source $TargetRoot /MIR /XD .git __pycache__ .venv node_modules build /NFL /NDL /NJH /NJS /nc /ns /np
if ($LASTEXITCODE -ge 8) {
    Write-Host "robocopy reported errors (exit $LASTEXITCODE). Check output."
    exit $LASTEXITCODE
}
Write-Host "Copy complete. Edit $TargetRoot\backend\.env -> ZY_BASE_DIR=$TargetRoot"
