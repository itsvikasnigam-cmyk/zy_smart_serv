# Force-stop every process listening on TCP 8081 and show what was killed.
# Usage: .\scripts\kill_port_8081.ps1

$port = 8081
Write-Host "=== netstat (port $port) ==="
netstat -ano | Select-String ":$port"

$pids = New-Object System.Collections.Generic.List[int]
foreach ($ln in (netstat -ano)) {
    $s = "$ln"
    if ($s -notmatch ":$port\s") { continue }
    if ($s -notmatch "LISTENING") { continue }
    if ($s -match "\s+(\d+)\s*$") {
        $p = [int]$Matches[1]
        if ($p -gt 0 -and -not $pids.Contains($p)) { [void]$pids.Add($p) }
    }
}

if ($pids.Count -eq 0) {
    Write-Host "No LISTENING PID found in netstat (port may be in TIME_WAIT only)."
}
else {
    Write-Host "`n=== Stopping PIDs ==="
    foreach ($listenerPid in $pids) {
        $proc = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "PID $listenerPid  $($proc.ProcessName)  $($proc.Path)"
            try {
                $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$listenerPid").CommandLine
                if ($cmd) { Write-Host "  cmd: $cmd" }
            }
            catch { }
        }
        else {
            Write-Host "PID $listenerPid  (process name unavailable)"
        }
        cmd /c "taskkill /PID $listenerPid /F" 2>&1 | ForEach-Object { Write-Host "  $_" }
    }
}

Start-Sleep -Seconds 2
Write-Host "`n=== netstat after kill ==="
$still = netstat -ano | Select-String ":$port" | Select-String "LISTENING"
if ($still) {
    Write-Host "WARN: port $port still LISTENING:"
    $still | ForEach-Object { Write-Host "  $_" }
    Write-Host ""
    Write-Host "Try: close all terminals running uvicorn/python, then run this script again."
    Write-Host "Or: Task Manager -> Details -> end python.exe using port 8081."
    Write-Host "Last resort: restart the PC."
    exit 1
}
Write-Host "OK: port $port has no LISTENING sockets."
