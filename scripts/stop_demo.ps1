$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$State = Join-Path $Root "backend\var\demo-processes.json"

if (-not (Test-Path -LiteralPath $State)) {
    Write-Host "No OpsBridge demo state file was found."
    exit 0
}

$Record = Get-Content -LiteralPath $State -Raw | ConvertFrom-Json
foreach ($Id in @($Record.api_pid, $Record.web_pid)) {
    $Process = Get-CimInstance Win32_Process -Filter "ProcessId = $Id" -ErrorAction SilentlyContinue
    if (-not $Process) { continue }
    $Command = [string]$Process.CommandLine
    if (-not $Command.Contains($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to stop PID $Id because it is not an OpsBridge process."
    }
    Stop-Process -Id $Id -Force
}

Remove-Item -LiteralPath $State -Force
Write-Host "OpsBridge demo processes stopped. Local database data was preserved."
