param(
    [ValidateRange(1024, 65535)]
    [int]$BackendPort = 8000,
    [ValidateRange(1024, 65535)]
    [int]$FrontendPort = 5173,
    [ValidatePattern('^[A-Za-z0-9_.-]+\.db$')]
    [string]$DatabaseFile = "opsbridge.db"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$Node = (Get-Command node -ErrorAction Stop).Source
$Vite = Join-Path $Frontend "node_modules\vite\bin\vite.js"
$State = Join-Path $Backend "var\demo-processes.json"
$DatabaseUrl = "sqlite+pysqlite:///./var/$DatabaseFile"

function Assert-PortAvailable([int]$Port, [string]$Label) {
    $Listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try {
        $Listener.Start()
    }
    catch {
        throw "$Label port $Port is already in use. Choose another port; no existing process was changed."
    }
    finally {
        $Listener.Stop()
    }
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Backend environment missing. Run backend\scripts\setup.ps1 first."
}
if (-not (Test-Path -LiteralPath $Vite)) {
    throw "Frontend dependencies missing. Run pnpm install --frozen-lockfile in frontend."
}
if (Test-Path -LiteralPath $State) {
    throw "A demo state file already exists. Run scripts\stop_demo.ps1 or inspect backend\var\demo-processes.json."
}
Assert-PortAvailable -Port $BackendPort -Label "Backend"
Assert-PortAvailable -Port $FrontendPort -Label "Frontend"

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $State) | Out-Null
$PreviousDatabase = $env:OPSBRIDGE_DATABASE_URL
$PreviousOrigin = $env:OPSBRIDGE_FRONTEND_ORIGIN
$PreviousTarget = $env:OPSBRIDGE_API_TARGET
try {
    $env:OPSBRIDGE_DATABASE_URL = $DatabaseUrl
    $env:OPSBRIDGE_FRONTEND_ORIGIN = "http://127.0.0.1:$FrontendPort"
    $env:OPSBRIDGE_API_TARGET = "http://127.0.0.1:$BackendPort"
    Push-Location $Backend
    try {
        & $Python -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "Alembic upgrade failed." }
        & $Python -m opsbridge.cli.seed_knowledge
        if ($LASTEXITCODE -ne 0) { throw "Knowledge seed failed." }
    }
    finally { Pop-Location }

    $Api = Start-Process -FilePath $Python -ArgumentList @(
        "-m", "uvicorn", "opsbridge.main:app", "--host", "127.0.0.1", "--port", "$BackendPort"
    ) -WorkingDirectory $Backend -WindowStyle Hidden -PassThru
    $Web = Start-Process -FilePath $Node -ArgumentList @(
        $Vite, "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort"
    ) -WorkingDirectory $Frontend -WindowStyle Hidden -PassThru

    $Ready = $false
    foreach ($Attempt in 1..40) {
        if ($Api.HasExited) { throw "Backend process exited before becoming ready." }
        if ($Web.HasExited) { throw "Frontend process exited before becoming ready." }
        try {
            $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/health/ready" -TimeoutSec 1
            if ($Health.status -eq "ready") { $Ready = $true; break }
        }
        catch { Start-Sleep -Milliseconds 250 }
    }
    if (-not $Ready) { throw "Backend did not become ready within 10 seconds." }

    [pscustomobject]@{
        root = $Root
        api_pid = $Api.Id
        web_pid = $Web.Id
        backend_port = $BackendPort
        frontend_port = $FrontendPort
        started_at = (Get-Date).ToUniversalTime().ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $State -Encoding UTF8
}
catch {
    if ($Api -and -not $Api.HasExited) { Stop-Process -Id $Api.Id -Force }
    if ($Web -and -not $Web.HasExited) { Stop-Process -Id $Web.Id -Force }
    throw
}
finally {
    $env:OPSBRIDGE_DATABASE_URL = $PreviousDatabase
    $env:OPSBRIDGE_FRONTEND_ORIGIN = $PreviousOrigin
    $env:OPSBRIDGE_API_TARGET = $PreviousTarget
}

Write-Host "OpsBridge demo started on http://127.0.0.1:$FrontendPort"
Write-Host "Create local users interactively before login; no default password is installed."
Write-Host "Stop with: .\scripts\stop_demo.ps1"
