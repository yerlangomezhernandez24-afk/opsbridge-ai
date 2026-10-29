# Fase 2.3B — API REST de tickets, autorización, concurrencia e idempotencia

**Responsable:** Yerlan Daniel Gómez Hernández  
**Fecha:** 2026-10-28  
**Decisión:** **GO técnico**, pendiente de revisión

## Resultado

Se implementó la primera API funcional de tickets sobre el dominio y persistencia reales. Los controladores validan HTTP; `TicketService` coordina autorización y transacciones; el agregado conserva reglas; SQLAlchemy persiste con control optimista. No se implementaron frontend, IA, RAG, comentarios, integraciones ni aprobaciones.

Endpoints:

- `POST /api/v1/tickets`: S/T, CSRF+Origin, UUID `Idempotency-Key`, respuesta `201`, `Location` y ETag.
- `GET /api/v1/tickets`: S solo propios; T/A todos; filtros, búsqueda parametrizada y cursor, máximo 100.
- `GET /api/v1/tickets/{id}`: S propietario; T/A; ETag.
- `PATCH /api/v1/tickets/{id}`: T autorizado; categoría/impacto/urgencia; `If-Match` obligatorio.
- `POST /api/v1/tickets/{id}/transitions`: S propietario/T autorizado según dominio; `If-Match` obligatorio.
- `GET /api/v1/tickets/{id}/timeline`: misma visibilidad; paginación por revisión.

## Seguridad y autorización

La identidad siempre procede de la sesión. Los esquemas `extra=forbid` rechazan `requester_id`, rol, estado o versión inyectados. El listado de requester incluye el predicado de propietario en SQL; detalle y mutaciones ocultan tickets ajenos con el mismo `404`. Técnicos no pueden modificar tickets asignados a otro técnico. Aprobadores tienen lectura pero no mutación. CSRF y Origin se vuelven a validar incluso en repeticiones idempotentes.

Las búsquedas usan expresiones SQLAlchemy parametrizadas y escapan comodines. Las respuestas omiten `requester_id`, hashes, cookies, SQL y rutas. Errores usan `application/problem+json` con 400/401/403/404/409/412/422/428/503 diferenciados.

## ETag y concurrencia

ETag es `"<version>"`, sin datos sensibles. PATCH y transiciones exigen `If-Match`; ausencia devuelve 428, formato inválido 400, versión obsoleta 412. La precondición HTTP se complementa con `UPDATE ... WHERE id AND version` transaccional. Dos PATCH HTTP simultáneos sobre el mismo ETag produjeron exactamente un 200 y un 412; el perdedor no creó eventos ni sobrescribió.

## Idempotencia

La migración `0003_ticket_api_idempotency` crea `idempotency_records` con FK a usuario/ticket, unicidad por usuario+operación+clave, huella, instantánea de respuesta y expiración. La reserva, ticket, evento, contador y respuesta se confirman o revierten juntos. Se comprobaron repetición idéntica, conflicto de carga, misma clave entre usuarios, carrera de dos solicitudes, reinicio, rollback/reintento y reproducción del estado original tras una transición. Retención: 24 h; limpieza oportunista.

## Migraciones y pruebas

Línea base: **187 aprobadas**. Cierre final:

Versiones importadas en el entorno verificado: Python 3.12.14, SQLite 3.53.1, FastAPI 0.162.0, SQLAlchemy 2.1.6, Alembic 1.20.1, Pydantic 2.14.1, Uvicorn 0.54.0, pytest 9.2.0, Ruff 0.17.3 y mypy 2.4.0.

- Ruff check: aprobado.
- Ruff format: aprobado, 84 archivos.
- mypy estricto: aprobado, 78 archivos.
- pytest: **203 aprobadas, 0 fallidas** en 40.23 s.
- `pip check`: limpio.
- Migración: upgrade desde `0002`, downgrade a `0002`, re-upgrade, `alembic check` sin diferencias y `0003_ticket_api_idempotency (head)`.
- Uvicorn real: `127.0.0.1:8767`, health `ok/ready`, OpenAPI con cuatro paths de tickets y respuesta `TicketEnvelope`; proceso detenido.
- Auditoría CVE dedicada: no ejecutada porque `pip-audit` no está instalado; no se inventa resultado.

La prueba `test_reproducible_vpn_business_scenario` ejecuta por HTTP real de TestClient: login requester, creación VPN, clave/ETag, lectura técnica, transición, rechazo obsoleto, IDOR de otro requester, replay sin duplicado y timeline final. Todos los datos son sintéticos.

## Problemas encontrados y corregidos

1. Ampliar el constructor requester rompía una prueba/invariante histórica. Se restauró y se añadió `create_by_technician`, conservando actor técnico en auditoría.
2. Un primer diseño idempotente guardaba solo el ticket y habría devuelto estado actualizado al repetir. Se corrigió almacenando la instantánea original saneada.
3. La política técnica inicial permitía PATCH sobre ticket asignado a otro técnico. Se añadió el control de asignación antes de mutar.
4. La primera inserción del test de migración quedó en una sección incorrecta; se corrigió y todas las migraciones se repitieron.

## Desviaciones y riesgos residuales

- La categoría es obligatoria al crear porque el dominio no admite ausencia; `context` se rechaza hasta modelarlo, en vez de descartarlo.
- PATCH no edita título/descripcion y requester no dispone de campos editables respaldados por el agregado actual.
- Comentarios, endpoint de asignación y exportación permanecen fuera: no existe modelo de dominio aprobado.
- El cursor es opaco/estricto y nunca autoriza, pero no está firmado; endurecer antes de exposición no local.
- Idempotencia de transiciones no se adelantó: el alcance exigía creación. Las transiciones sí tienen ETag y transacción.
- SQLite, rate limit por proceso, ausencia de TLS local y falta de auditoría CVE dedicada siguen siendo límites conocidos.

## Comandos ejecutados

```powershell
.\backend\scripts\test.ps1
Push-Location .\backend
.\.venv\Scripts\python.exe -m alembic downgrade 0002_local_auth
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m alembic current
Pop-Location
.\backend\.venv\Scripts\python.exe -m uvicorn opsbridge.main:app --app-dir backend/src --host 127.0.0.1 --port 8767
```

## Recomendación

Revisar este GO antes de autorizar la siguiente etapa. La próxima subfase debería completar comentarios/asignación solo después de diseñar su dominio, o iniciar frontend contra el OpenAPI estable si se autoriza expresamente. No avanzar automáticamente a frontend ni IA.
