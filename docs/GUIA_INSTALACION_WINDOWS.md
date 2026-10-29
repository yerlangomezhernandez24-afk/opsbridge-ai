# Guía de instalación local en Windows

## Requisitos

- Windows 11 x64, Python 3.12, Git opcional, Node 24 y pnpm 11. Python 3.11 no fue probado.
- No requiere administrador, Docker, Ollama ni cambios de `ExecutionPolicy`.

## Instalación limpia

```powershell
cd C:\ruta\OpsBridge_AI\backend
.\scripts\setup.ps1
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
pnpm install --frozen-lockfile
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

Si PowerShell bloquea scripts por una política corporativa, ejecute manualmente los comandos mostrados; no cambie la política global del equipo.

## Usuarios locales

Desde `backend`, ejecute tres veces. La contraseña se solicita sin eco y nunca se acepta como argumento:

```powershell
.\scripts\create-user.ps1 --login demo.requester --display-name "Demo Requester" --role requester
.\scripts\create-user.ps1 --login demo.technician --display-name "Demo Technician" --role technician
.\scripts\create-user.ps1 --login demo.approver --display-name "Demo Approver" --role approver
```

No existen credenciales predeterminadas. Use contraseñas distintas de las reales.

## Inicio y parada

```powershell
cd C:\ruta\OpsBridge_AI
# Use un puerto libre. En el equipo auditado, DataTrust ocupa 8000:
.\scripts\start_demo.ps1 -BackendPort 8768
```

Abra `http://127.0.0.1:5173`; OpenAPI está en `http://127.0.0.1:8768/docs` para el comando anterior. El script verifica puertos antes de iniciar y espera readiness; nunca detiene un proceso ajeno. Los procesos se inician ocultos y sus PID se guardan en el directorio ignorado `backend/var`. Para finalizar:

```powershell
.\scripts\stop_demo.ps1
```

La parada valida que los PID pertenezcan a comandos dentro del proyecto y preserva la base. Si el script fue interrumpido, inspeccione `backend/var/demo-processes.json` y los puertos con `Get-NetTCPConnection` antes de actuar.

## Inicio manual

Terminal 1:

```powershell
cd backend
$env:OPSBRIDGE_DATABASE_URL='sqlite+pysqlite:///./var/opsbridge.db'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m opsbridge.cli.seed_knowledge
.\.venv\Scripts\python.exe -m uvicorn opsbridge.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd frontend
$env:OPSBRIDGE_API_TARGET='http://127.0.0.1:8000'
pnpm dev
```

Detenga cada servidor con `Ctrl+C`. No deje procesos activos.

## Datos y migraciones

- La base local predeterminada es `backend/var/opsbridge.db`, ignorada por Git.
- `alembic current`, `alembic upgrade head` y `alembic check` verifican esquema.
- No borre una base con información valiosa. Downgrade solo sobre copias desechables.
- El corpus sintético se carga idempotentemente con `python -m opsbridge.cli.seed_knowledge`.
