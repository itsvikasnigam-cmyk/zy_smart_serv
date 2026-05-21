# Launch WSL llama.cpp inference stub (Chat Y). Ollama :11435 remains primary on Windows.
#
#   .\scripts\start_wsl_llama.ps1 -Role owner -Port 8082
#   .\scripts\start_wsl_llama.ps1 -Role sales -Port 8083
#
# Set in WSL profile or pass via env:
#   LLAMA_SERVER_BIN, LLAMA_MODEL_PATH

param(
    [ValidateSet('owner', 'sales')]
    [string]$Role = 'owner',
    [int]$Port = 8082
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$script = Join-Path $root 'scripts\wsl\start_llama_inference.sh'
if (-not (Test-Path $script)) {
    throw "Missing $script"
}

if ($Role -eq 'sales' -and $Port -eq 8082) {
    $Port = 8083
}

Write-Host "WSL llama inference: role=$Role port=$Port (Ctrl+C in WSL to stop)"
wsl bash -lc "cd '$(wsl wslpath -a $root)' && chmod +x scripts/wsl/start_llama_inference.sh && ./scripts/wsl/start_llama_inference.sh $Role $Port"
