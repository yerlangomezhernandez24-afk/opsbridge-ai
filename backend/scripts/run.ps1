param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$BackendDirectory = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BackendDirectory ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment not found. Run backend\scripts\setup.ps1 first."
}

Push-Location $BackendDirectory
try {
    & $Python -m uvicorn opsbridge.main:app --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
}

