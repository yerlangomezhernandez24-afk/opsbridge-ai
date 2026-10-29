# Fase 5 — Auditoría final local

**Fecha:** 2026-10-28  
**Resultado:** `GO condicionado para portafolio local`; 0 P0/P1 conocidos; P2 documentados.

## Entorno

- Windows 11 Home 64-bit, build 10.0.26200.
- Intel Core i7-10510U, 4 cores/8 lógicos; 11.81 GiB RAM (2.17 GiB libres durante inventario); Intel UHD, 1 GiB reportado; 369.71 GiB libres.
- Python 3.12.14; Node 24.22.1; pnpm 11.25.0; Git 2.53.0.
- FastAPI 0.162.0, SQLAlchemy 2.1.6, Alembic 1.20.1, Pydantic 2.14.1, Uvicorn 0.54.0, SQLite 3.53.1.

## Matriz de evidencia

| Criterio | Estado | Evidencia / comando |
|---|---|---|
| Backend lint/formato | Pass | `ruff format --check .`; `ruff check .`; 96 archivos |
| Tipado estricto | Pass | `mypy src tests`; 88 archivos |
| Backend completo | Pass | `pytest -q`; 211 aprobadas, 0 fallidas, 41.93 s |
| Dependencias Python coherentes | Pass | `pip check`; sin roturas |
| CVE Python | Not Tested | `pip-audit` no instalado; no se equipara `pip check` con auditoría |
| Frontend estricto | Pass | `pnpm typecheck`; `pnpm lint` |
| Componentes | Pass | `pnpm test`; 3 aprobadas |
| Build | Pass con P2 | Vite 8.3.5; 672.30 kB JS / 200.59 kB gzip; warning de chunk |
| E2E navegador | Pass | Playwright Chrome; 3 recorridos, 19.9 s; prueba dirigida integrada 1/1 |
| Accessibility | Pass limitado | axe sin serious/critical en Fase 3; teclado/viewports revisados. El focus trap pendiente en este corte fue corregido y verificado en la auditoría independiente posterior. |
| Viewports | Pass | 360×800, 390×844, 768×1024, 1366×768, 1920×1080; sin overflow global |
| Firefox/Safari | Not Tested | binarios/plataforma no disponibles en el entorno verificado |
| Sesión/CSRF/Origin/rate-limit | Pass | pruebas auth: cookie HttpOnly/SameSite, origen exacto, CSRF, revocación, expiración, 429 |
| RBAC/IDOR/BOLA | Pass | pruebas multicuenta de ticket propio/ajeno; 404 uniforme; roles de propuesta/decisión |
| Separación de funciones | Pass | proponente técnico, decisor aprobador distinto, ejecutor proponente; denegaciones probadas |
| ETag/idempotencia/concurrencia | Pass | carreras HTTP existentes; 200/412; creación única; reinicio y rollback |
| Acción exactamente una vez | Pass | dos ejecuciones concurrentes: 200/409; una fila y `reset_count=1` |
| Migración base vacía/anterior | Pass | upgrade a `0005`, downgrade/re-upgrade en suite y `alembic check` limpio |
| FK/WAL/bloqueo SQLite | Pass backend base | PRAGMA FK/WAL; bloqueo dirigido en persistencia; uniformidad HTTP nueva queda P2 |
| Retrieval/citas/permisos | Pass | 13 casos tras auditoría independiente; recall@3 1.0, precision@3 1.0, abstención 1.0; documento restringido 404 |
| Prompt injection/tool abuse | Pass limitado | contenido adversarial queda citado como dato; schema/allowlist/hash impiden efecto no autorizado |
| LLM real | Not Tested | Ollama ausente; UI/API reportan `LOCAL_LLM_PENDING` |
| npm CVE | Pass al corte | `pnpm audit --audit-level low`; sin vulnerabilidades conocidas |
| Instalación Python 3.11 | Not Tested | ejecutable no disponible |
| Loopback | Pass | Uvicorn `127.0.0.1:8768`; Vite `127.0.0.1:5173`; CORS exacto |
| Secretos/artefactos | Pass limitado | `.env`/DB/node_modules/reportes ignorados; no hay Git local; revisión por patrones sin credenciales reales |

## Rendimiento observado

Medición local secuencial sobre Uvicorn/SQLite, base sintética pequeña y sesión técnica; no es SLA ni prueba de carga. PowerShell `Invoke-WebRequest`, warm process:

| Endpoint | N | mediana | p95 | máximo |
|---|---:|---:|---:|---:|
| `/health/ready` | 50 | 5.50 ms | 7.84 ms | 32.55 ms |
| `/api/v1/tickets?page_size=100` | 30 | 20.83 ms | 22.81 ms | 23.42 ms |
| `/api/v1/knowledge/search?...` | 30 | 17.01 ms | 19.96 ms | 21.11 ms |

No se midió concurrencia sostenida, memoria del proceso ni escala empresarial. SQLite sigue siendo una restricción deliberada.

## Revisión visual

Se inspeccionaron capturas reales de login/dashboard/listado/detalle/móvil y las nuevas vistas:

- `screenshots/phase4-knowledge-desktop.png`
- `screenshots/phase4-approval-desktop.png`
- `screenshots/phase4-execution-desktop.png`

No se observaron clipping, overflow global, botones sin respaldo o afirmaciones engañosas. Se corrigió el score BM25 negativo expuesto. La lista de múltiples propuestas es legible, aunque futuras demos deberían partir de una base limpia para no acumular registros.

## Hallazgos y decisión

Se corrigieron tres P2 durante la auditoría. Los pendientes están en `ISSUES_PENDIENTES.md`. No se identificó un bypass P0 ni un recorrido central P1 roto. El producto recibe **GO condicionado como demo local de portafolio**, no como producto público o empresarial. El LLM real permanece NO GO/pendiente y no bloquea Rules, FTS5 ni el simulador gobernado.
