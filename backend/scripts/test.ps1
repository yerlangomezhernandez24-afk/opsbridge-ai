$ErrorActionPreference = "Stop"
$BackendDirectory = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BackendDirectory ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment not found. Run backend\scripts\setup.ps1 first."
}

function Invoke-PythonChecked {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
}

Push-Location $BackendDirectory
try {
    Invoke-PythonChecked -Arguments @("-m", "ruff", "check", ".")
    Invoke-PythonChecked -Arguments @("-m", "ruff", "format", "--check", ".")
    Invoke-PythonChecked -Arguments @("-m", "mypy")
    Invoke-PythonChecked -Arguments @("-m", "pytest")
    Invoke-PythonChecked -Arguments @("-m", "pip", "check")
}
finally {
    Pop-Location
}

