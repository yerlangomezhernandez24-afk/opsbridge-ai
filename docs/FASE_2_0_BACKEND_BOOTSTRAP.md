# Informe técnico — Fase 2.0 Backend Bootstrap

**Fecha de ejecución:** 2026-10-28  
**Estado:** GO  
**Responsable:** Yerlan Daniel Gómez Hernández  
**Alcance:** bootstrap local; sin tickets, RBAC, RAG, IA, agentes ni frontend

## 1. Resultado

Se creó un paquete Python instalable con FastAPI, configuración Pydantic, logging JSON saneado, manejo centralizado de errores, SQLAlchemy/Alembic sin entidades empresariales, scripts PowerShell y pruebas automatizadas. La aplicación inicia en loopback, responde liveness/readiness y publica OpenAPI. No se modificó DataTrust, no se usaron servicios pagados y no se publicó contenido.

## 2. Entorno realmente verificado

| Componente | Evidencia |
|---|---|
| Sistema operativo | Microsoft Windows 11 Home, versión 10.0.26200, 64 bits, AMD64 |
| CPU | Intel Core i7-10510U |
| Python de usuario | No instalado/accesible; `python.exe` es alias de Microsoft Store y `py` no existe |
| Python de verificación | Runtime aislado de Codex: CPython 3.12.14, 64 bits |
| pip | 26.2.2 |
| SQLite | 3.53.1; FTS5 habilitado |
| Git | 2.53.0.windows.3 |
| Node.js informativo | 24.22.1 del runtime de Codex; pnpm 11.25.0; `npm` no está en PATH |
| Repositorio Git | No inicializado; no hubo commit, remoto ni publicación |

El paquete declara `requires-python = ">=3.11,<3.13"`. Python 3.12.14 está probado; Python 3.11 queda pendiente porque no está instalado en el equipo.

## 3. Dependencias directas instaladas

| Uso | Versión |
|---|---:|
| FastAPI | 0.162.0 |
| Pydantic | 2.14.1 |
| pydantic-settings | 2.16.2 |
| SQLAlchemy | 2.1.6 |
| Alembic | 1.20.1 |
| Uvicorn | 0.54.0 |
| httpx2 (pruebas Starlette) | 2.16.0 |
| pytest | 9.2.0 |
| Ruff | 0.17.3 |
| mypy | 2.4.0 |

`backend/requirements.lock` conserva también las versiones transitivas resueltas; su SHA-256 al cierre fue `21294EC1BB21EB7E089F87BC0EB15911D04961946DDC49262DE46709A111A05A`. Se sustituyó `httpx` por `httpx2` porque Starlette 1.10.0 emitía una deprecación explícita al usar el cliente anterior.

## 4. Componentes creados

- `backend/pyproject.toml`: metadatos, dependencias exactas y configuración de pytest/Ruff/mypy.
- `backend/requirements.lock`: resolución completa comprobada en Windows/Python 3.12.
- `backend/src/opsbridge/`: dominio de salud, caso de uso, configuración, DB, observabilidad y FastAPI.
- `backend/alembic/` y `alembic.ini`: entorno listo sin revisión ficticia ni tablas.
- `backend/tests/`: configuración, importación, factoría, health, OpenAPI, transacciones, errores y redacción.
- `backend/scripts/`: instalación, calidad y arranque PowerShell.
- `backend/.env.example`: variables no secretas; `.env` real queda ignorado.
- `.gitignore`: venvs, secretos, DB, logs, cachés y artefactos.

La estructura respeta `presentation -> application -> domain` e inyecta adaptadores concretos desde la factoría. No se añadieron interfaces abstractas o módulos de negocio vacíos.

## 5. Seguridad implementada en este alcance

- Host validado como loopback; `0.0.0.0`, IP LAN y hostname externo se rechazan.
- `debug=false` por defecto y FastAPI siempre responde sin modo debug.
- SQLite es el único esquema de DB aceptado en Fase 2.0.
- Sin CORS: no se añadió middleware permisivo antes de existir frontend.
- Problem Details controlado para errores de aplicación, validación, HTTP y excepciones no previstas.
- Respuestas 500 no contienen excepción ni traceback.
- Logs JSON no incluyen query/body y redactan password, token, secret, Authorization y Bearer.
- `.env`, bases, logs y venvs quedan ignorados.
- No existen credenciales, autenticación incompleta ni endpoints empresariales.

## 6. Persistencia preparada

- `Database` crea un engine SQLAlchemy con `pool_pre_ping` y ajuste SQLite para FastAPI.
- El context manager de sesión confirma al éxito, revierte ante excepción y siempre cierra.
- Readiness ejecuta `SELECT 1` sin revelar URL o ruta.
- Alembic carga la metadata de `Base`; `alembic check` devolvió `No new upgrade operations detected`.
- No existe ninguna entidad ni revisión: la primera migración corresponde a la fase de dominio/persistencia revisada.
- Las pruebas usan rutas SQLite dentro del directorio temporal de pytest.

## 7. Comandos ejecutados y evidencia

Inventario principal:

```powershell
Get-CimInstance Win32_OperatingSystem
py -0p
python --version
git --version
node --version
<runtime-python> -c "... sqlite3 ... ENABLE_FTS5 ..."
<runtime-python> -m pip index versions <paquete>
```

Instalación inicial limpia:

```powershell
<runtime-python> -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install --editable ".[dev]"
```

Reproducción independiente desde lock:

```powershell
<runtime-python> -m venv .venv-verify
.\.venv-verify\Scripts\python.exe -m pip install -r requirements.lock
.\.venv-verify\Scripts\python.exe -m pip install --no-deps --editable .
.\.venv-verify\Scripts\python.exe -m pip check
.\.venv-verify\Scripts\python.exe -m pytest -q
```

Resultado: `No broken requirements found` y `14 passed in 0.53s`.

Calidad y persistencia:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic check
```

Arranque real:

```powershell
.\.venv\Scripts\python.exe -m uvicorn opsbridge.main:app --host 127.0.0.1 --port 8765
Invoke-WebRequest http://127.0.0.1:8765/health/live
Invoke-WebRequest http://127.0.0.1:8765/health/ready
Invoke-RestMethod http://127.0.0.1:8765/openapi.json
```

Resultados: liveness `200`, readiness `200`, OpenAPI `0.1.0` con solo `/health/live` y `/health/ready`. Uvicorn terminó limpiamente con `Ctrl+C`.

## 8. Pruebas aprobadas y defectos corregidos

Suite final mediante `scripts/test.ps1`: **14 aprobadas, 0 fallidas en 0.47 s**; Ruff, formato, mypy y `pip check` también aprobados.

Cobertura funcional de la suite:

1. Importación y versión del paquete.
2. Creación y metadatos de la aplicación.
3. Liveness, readiness y conexión SQLite.
4. Contrato OpenAPI limitado al alcance.
5. Valores seguros de configuración.
6. Rechazo de host no loopback, DB no SQLite y debug inseguro.
7. Commit/rollback real con DB temporal.
8. Error 500 sin trazas o texto de excepción.
9. Redacción de secretos en logs.

Durante la construcción falló inicialmente la prueba de redacción porque `authorization=Bearer valor` dejaba el valor tras sustituir `Bearer`. Se corrigió el patrón y la prueba dirigida pasó. La primera suite completa registró `13 passed, 1 failed`; no se presenta como aprobada. La suite posterior quedó limpia.

## 9. Limitaciones y observaciones

- El equipo no tiene Python normal accesible; fuera de Codex se debe instalar Python 3.12 x64 antes de usar `setup.ps1`.
- Python 3.11 está permitido por metadata y dependencias, pero no fue ejecutado localmente.
- El puerto 8000 estaba ocupado por un proceso ajeno. No se detuvo; la prueba real usó 8765. `run.ps1` acepta `-Port` para este caso.
- `.venv-verify` es un entorno local ignorado creado para la segunda instalación. La herramienta bloqueó su eliminación recursiva por política de seguridad; no contiene código ni secretos y puede borrarse manualmente cuando no se necesite.
- No se ejecutó auditoría CVE dedicada; queda para una puerta de seguridad posterior. `pip check` sí confirmó integridad de dependencias.
- No hay tablas, migraciones, autenticación ni lógica empresarial por restricción expresa de Fase 2.0.

## 10. Criterios de aceptación

| Criterio | Estado | Evidencia |
|---|---|---|
| Instalación sin errores conocidos | Cumplido | Dos venvs; lock; `pip check` limpio |
| FastAPI inicia | Cumplido | Uvicorn en loopback:8765 |
| Health responde | Cumplido | Dos respuestas HTTP 200 |
| Pruebas pasan | Cumplido | 14/14 final y 14/14 en venv de verificación |
| Configuración sin secretos | Cumplido | `.env.example`, inspección y `.gitignore` |
| Estructura coincide | Cumplido | Monolito modular por capas; desviación Python documentada |
| Instalación reproducible | Cumplido con prerrequisito | Lock + `setup.ps1`; Python global pendiente en el equipo |
| DataTrust intacto | Cumplido | Trabajo limitado a OpsBridge_AI |
| Sin publicación | Cumplido | Carpeta sin `.git`; ningún remoto/servicio público |
| Evidencia documentada | Cumplido | Este informe y `PROJECT_STATE.md` |

## 11. Recomendación

Autorizar Fase 2.1 solo después de revisar este GO. El siguiente corte debe modelar exclusivamente el dominio de tickets y su máquina de estados con pruebas unitarias, sin adelantar autenticación, RAG, agentes o herramientas.

