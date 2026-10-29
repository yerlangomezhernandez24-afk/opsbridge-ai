param(
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
$BackendDirectory = Split-Path -Parent $PSScriptRoot
$VirtualEnvironment = Join-Path $BackendDirectory ".venv"
$VirtualPython = Join-Path $VirtualEnvironment "Scripts\python.exe"

if ($PythonExecutable) {
    $PythonCommand = $PythonExecutable
    $PythonArguments = @()
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCommand = "py"
    $PythonArguments = @("-3.12")
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCommand = "python"
    $PythonArguments = @()
}
else {
    throw "Python 3.12 was not found. Install it or pass -PythonExecutable with an explicit path."
}

Push-Location $BackendDirectory
try {
    & $PythonCommand @PythonArguments --version
    if ($LASTEXITCODE -ne 0) {
        throw "The selected Python launcher is unavailable. Install Python 3.12 or pass -PythonExecutable."
    }
    & $PythonCommand @PythonArguments -m venv $VirtualEnvironment
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
    & $VirtualPython -m pip install --upgrade pip
    & $VirtualPython -m pip install --constraint requirements.lock --editable ".[dev]"
    & $VirtualPython -m pip check
}
finally {
    Pop-Location
}

Write-Host "Backend environment ready at $VirtualEnvironment"

