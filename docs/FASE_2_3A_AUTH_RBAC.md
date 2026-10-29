# Fase 2.3A — Autenticación local, sesiones seguras y autorización base

**Responsable:** Yerlan Daniel Gómez Hernández  
**Fecha:** 2026-10-28  
**Decisión:** **GO técnico**, pendiente de revisión antes de Fase 2.3B

## Alcance implementado

- Identidades locales UUID v4 con login normalizado y roles cerrados `requester`, `technician`, `approver`.
- Contraseñas Argon2id con parámetros explícitos; creación interactiva sin contraseña en argumentos.
- Sesiones opacas persistidas con token aleatorio, solo verificador SHA-256 en SQL, expiración absoluta/inactiva, revocación y rotación al login.
- Endpoints exclusivos de autenticación: `POST /api/v1/auth/login`, `POST /api/v1/auth/logout` y `GET /api/v1/auth/session`.
- Cookie `HttpOnly`, `SameSite=Lax`, `Secure` configurable y excepción HTTP limitada a loopback.
- Origin exacto, CORS con credenciales sin comodín, CSRF ligado a sesión y respuestas `no-store`.
- Rate limiting local con reloj inyectable y respuesta `429`/`Retry-After`.
- Política RBAC de denegación por defecto con propiedad, asignación y separación de funciones. No se añadieron endpoints de tickets.
- Migración incremental `0002_local_auth`; `0001_ticket_persistence` permanece intacta.

## Modelo relacional

`users` conserva identidad, login único, nombre, hash de contraseña, rol, activación y timestamps UTC. `auth_sessions` conserva ID, FK al usuario, verificador único, creación/último uso, expiraciones y revocación. Existen checks de formato, rol y orden temporal, además de índices por usuario y expiración. ORM y dominio permanecen separados.

La Unit of Work confirma usuario/sesión de forma atómica o revierte. Una identidad duplicada se traduce a un conflicto controlado. La rehidratación rechaza UUID, roles o valores persistidos inválidos; no aplica defaults silenciosos.

## Matriz mínima de autorización

| Acción | Requester | Technician | Approver |
|---|---|---|---|
| Crear ticket | Sí | Sí | No |
| Ver ticket | Solo propio | Sí | Sí |
| Modificar | Propio en `new` | Sí | No |
| Trabajar | No | Solo asignado | No |
| Aprobar | No | No | Sí, excepto si solicitó o propuso |

Estas políticas están probadas como objetos de aplicación, pero su integración con casos de uso HTTP de tickets corresponde a Fase 2.3B.

## Evidencia ejecutada

Línea base previa: **168 pruebas aprobadas**. Cierre:

- `backend/scripts/test.ps1`: Ruff check aprobado; Ruff format aprobado (78 archivos); mypy estricto aprobado (73 archivos); pytest **187 aprobadas, 0 fallidas** en 10.75 s; `pip check` limpio.
- Pruebas nuevas: Argon2id/sal/verificación, tokens y CSRF, matriz RBAC, login/logout/session, cookies, Origin, mensajes genéricos, rate limit, fijación/rotación, usuario deshabilitado, expiración determinista, persistencia tras reinicio, rollback por duplicado, datos corruptos y OpenAPI.
- Alembic real sobre base desechable: `upgrade head`, `alembic check`, `downgrade 0002 -> 0001`, nuevo `upgrade head` y `current`; resultado `0002_local_auth (head)`.
- Migración incremental automatizada: un ticket creado bajo `0001` permaneció después de aplicar `0002`.
- Arranque real Uvicorn en `127.0.0.1:8766`: `/health/live` = `ok`, `/health/ready` = `ready`; OpenAPI expuso exactamente las tres rutas auth previstas además de health. El proceso se detuvo correctamente.
- Entorno virtual limpio temporal: instalación editable con lock, `pip check` e importación de `opsbridge`, Argon2, FastAPI y SQLAlchemy aprobadas.

## Comandos principales

```powershell
.\backend\scripts\test.ps1
Push-Location .\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m alembic downgrade 0001_ticket_persistence
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
Pop-Location
.\backend\scripts\create-user.ps1 --login demo.requester --display-name "Demo Requester" --role requester
```

El downgrade solo se ejecutó sobre una base desechable. No se migró ni borró una base del usuario.

## Versiones comprobadas

- Windows 11 Home x64 `10.0.26200`; Python `3.12.14`.
- FastAPI `0.162.0`; Pydantic `2.14.1`; pydantic-settings `2.16.2`.
- SQLAlchemy `2.1.6`; Alembic `1.20.1`; Uvicorn `0.54.0`.
- argon2-cffi `25.1.0`; argon2-cffi-bindings `26.1.0`.
- pytest `9.2.0`; Ruff `0.17.3`; mypy `2.4.0`.
- Git `2.53.0.windows.3`; Node `24.22.1` solo informativo.

## Seguridad, limitaciones y riesgos

1. SQLite y el rate limiter en memoria son adecuados para la demo local, no para múltiples procesos o carga empresarial.
2. No existe MFA, SSO, recuperación de contraseña ni administración HTTP de usuarios; no se afirma que existan.
3. `Secure=false` es una excepción de desarrollo loopback; un perfil TLS debe usar origen HTTPS y `Secure=true`.
4. Python 3.11 está permitido por metadatos pero no fue ejecutado; queda pendiente.
5. `pip-audit` no está instalado. `pip check` fue limpio, pero no equivale a auditoría CVE; se documenta como pendiente sin inventar resultado.
6. La política RBAC todavía no está conectada a endpoints de tickets porque esos endpoints quedaron expresamente fuera de alcance.
7. El entorno de verificación limpio y una base desechable quedaron ignorados bajo `.venv-verify-23a` y `backend/var/phase23a_runtime_verify.db`; la política de la herramienta impidió su borrado. No contienen secretos ni datos reales y no están versionados.

## Archivos principales creados o modificados

- Dominio/aplicación: `domain/identity.py`, `application/auth.py`, `application/authorization.py`, `application/ports/auth.py`.
- Infraestructura: `infrastructure/security/`, `infrastructure/db/identity_models.py`, `auth_repository.py`, `auth_unit_of_work.py`.
- HTTP/CLI: `presentation/http/routes/auth.py`, `presentation/http/app.py`, `cli/create_user.py`, `scripts/create-user.ps1`.
- Migración: `alembic/versions/0002_local_auth.py`.
- Configuración: `pyproject.toml`, `requirements.lock`, `.env.example`.
- Pruebas y documentación de esta fase, incluido `ADR-002`.

## Recomendación para Fase 2.3B

Tras revisión, implementar únicamente los casos de uso y endpoints HTTP de tickets conectando esta identidad y `AuthorizationPolicy` con el repositorio existente. Añadir ETag/control optimista e idempotencia conforme al contrato, con pruebas IDOR y matriz rol/propiedad. No incorporar frontend, IA, RAG, agentes ni integraciones externas.
