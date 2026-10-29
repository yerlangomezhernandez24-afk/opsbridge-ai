# Fase 3 — Frontend profesional e integración

**Fecha:** 2026-10-28  
**Estado:** **WEB_GO** para el recorrido central; capacidades de Fase 4 visibles como no habilitadas

## Resultado

Se implementó una SPA React/TypeScript/Vite integrada con la API real mediante proxy local. La sesión usa exclusivamente la cookie HttpOnly del backend; CSRF se obtiene desde `/auth/session`; las mutaciones de tickets conservan Origin, CSRF, `Idempotency-Key` y ETag. No existen credenciales predeterminadas en el cliente.

Pantallas implementadas: login, Operations Center con métricas derivadas, workspace de tickets con búsqueda/filtros, creación validada, detalle con timeline y transiciones, analítica basada en tickets, configuración/estado y vistas honestas deshabilitadas para aprobaciones, conocimiento e IA.

## Contrato verificado

| Área | Rutas reales usadas | Control |
|---|---|---|
| Sesión | `POST /api/v1/auth/login`, `GET /session`, `POST /logout` | cookie HttpOnly, Origin y CSRF |
| Tickets | `POST/GET /api/v1/tickets`, `GET/PATCH /{id}` | RBAC, propiedad, idempotencia, ETag |
| Flujo | `POST /{id}/transitions`, `GET /{id}/timeline` | `If-Match`, dominio y timeline persistido |
| Estado | `/health/ready` | respuesta mínima |

OpenAPI no declara todavía el esquema de seguridad cookie aunque el runtime sí lo exige; es una mejora P2 de documentación, no un bypass.

## Toolchain comprobado

- Node.js 24.22.1; pnpm 11.25.0; npm no disponible en PATH.
- React 19.3.1, Vite 8.3.5, TypeScript 6.0.3, Playwright 1.64.1.
- `pnpm typecheck`: aprobado.
- `pnpm lint`: aprobado.
- `pnpm test`: 3 pruebas de componentes aprobadas.
- `pnpm build`: aprobado; JS 667.13 kB (199.31 kB gzip), advertencia P2 de chunk mayor a 500 kB.
- Playwright Chrome local: 2 E2E aprobadas en 11.4 s.
- axe: cero violaciones serious/critical en detalle; detectó inicialmente contraste 4.47:1 y se corrigió el token.
- Viewports comprobados: 360×800, 390×844, 768×1024, 1366×768 y 1920×1080; sin overflow global.

## Defectos corregidos durante integración

1. El primer cliente usó vocabularios ilustrativos distintos del dominio; la API devolvió 422. Se alinearon categoría `network.vpn`, impacto y estados con los enums reales.
2. TypeScript 7 no era compatible con la versión verificada de typescript-eslint; se fijó TypeScript 6.0.3.
3. axe encontró contraste 4.47:1; se elevó el contraste del token `--muted`.
4. Una franja del sidebar quedaba visible en móvil; se corrigió el estado cerrado y se repitió la captura.
5. El puerto 8000 estaba ocupado por un proceso ajeno; la verificación usó 8768 sin detenerlo.

## Evidencia visual

- `docs/screenshots/phase3-overview-desktop.png`
- `docs/screenshots/phase3-ticket-detail-desktop.png`
- `docs/screenshots/phase3-ticket-detail-mobile.png`
- `docs/screenshots/phase3-technician-workspace.png`

Los datos son sintéticos y proceden de una base temporal ignorada. No contienen tokens ni contraseñas.

## Límites

- Knowledge, aprobaciones e IA permanecen deshabilitados hasta Fase 4.
- Safari y Firefox no fueron ejecutados; Chrome instalado sí.
- El bundle requiere división antes de una release final si el tamaño continúa creciendo.
- La prueba E2E requiere cuentas sintéticas creadas previamente y la contraseña por variable `OPSBRIDGE_E2E_PASSWORD`.

## Comandos principales

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm typecheck
pnpm lint
pnpm test
pnpm build
$env:OPSBRIDGE_E2E_PASSWORD='<contraseña sintética local>'
pnpm test:e2e
```
