# Cierre de hallazgos de auditoría final

**Proyecto:** OpsBridge AI `v1.0.0-rc.1`  
**Corte:** 2026-10-29  
**Decisión:** **GO para revisión humana local**; **NO GO para publicación automática o producción**.

## 1. Hallazgos resueltos

1. **Transiciones frontend/backend.** La interfaz ya no contiene una matriz de estados independiente. Consulta `GET /api/v1/tickets/{ticket_id}/transition-options`, muestra únicamente las opciones autorizadas y solicita `reason`, `resolution_summary`, `requester_response_received` o `requester_confirmed` cuando el servidor lo exige.
2. **Aprobación no confiable del cliente.** `approval_resolved` y `approval_reference` se retiraron del DTO HTTP. Los campos desconocidos producen `422` y la API bloquea las transiciones genéricas hacia/desde `waiting_approval` hasta disponer de evidencia de aprobación persistida y verificable.
3. **Automatización sobre tickets inválidos.** El reset VPN exige ticket `in_progress`, categoría VPN, asignación al técnico y versión vigente al proponer, decidir y ejecutar. Una cancelación o cambio posterior invalida la propuesta y no crea ejecución ni efecto simulado.
4. **Idempotencia en reintentos.** El formulario conserva una única `Idempotency-Key` durante todos los reintentos de la misma creación; una prueba de componente comprueba igualdad de cabecera tras un fallo de red.
5. **Timeline mayor que el límite visible.** La UI consume `meta.has_more` y declara “Mostrando los primeros 100 eventos” en lugar de presentar el subconjunto como historial completo.
6. **E2E empresarial.** El recorrido real ahora incluye `new → triaged → in_progress`, propuesta, aprobación independiente, ejecución simulada, resolución con resumen y cierre confirmado por el solicitante.

Los P2 de bundle dividido, duración real de herramientas, traducción de errores SQLite y rutas documentales portables ya estaban aplicados en el corte anterior y se conservaron. El build mantiene un chunk diferido de gráficos.

## 2. Evidencia de seguridad y regresión

| Comprobación | Resultado real |
|---|---|
| pytest, entorno principal | **215 passed**, 39.12 s |
| pytest, entorno virtual nuevo | **215 passed**, 39.09 s |
| Ruff lint / format | aprobado; 88 archivos formateados |
| mypy `--strict` | aprobado; 63 archivos fuente |
| `pip check` | sin dependencias rotas en ambos entornos |
| `pip-audit` | sin vulnerabilidades conocidas; paquete editable local omitido |
| TypeScript / ESLint | aprobados |
| Vitest | **7 passed** |
| Vite build | aprobado; JS principal 303.31 kB y gráficos diferidos 374.56 kB |
| `pnpm audit --audit-level high` | sin vulnerabilidades conocidas |
| Playwright Chrome | **4 passed**, 37.8 s |
| Alembic | vacío → head, downgrade a base, re-upgrade y `check` aprobados |

Durante una repetición conjunta de Vitest y build, una prueba de login agotó su espera y dejó el DOM vacío. La misma prueba aislada aprobó inmediatamente y la suite completa repetida finalizó **7/7** en 3.38 s; se registra como intermitencia observada, no como resultado oculto.

Las pruebas negativas verifican IDOR, CSRF, ETag obsoleto, replay de idempotencia, separación de funciones, doble decisión, doble ejecución, afirmaciones de aprobación del cliente, propuesta fuera de estado y cancelación posterior a la aprobación sin efecto.

## 3. Migraciones, instalación y ejecución

- Instalación limpia con Python 3.12 mediante `backend/.venv-blockers-verify`, constraints de `requirements.lock` e instalación editable `.[dev]`: aprobada.
- Migraciones `0001`–`0005` probadas sobre base desechable; no se alteró ninguna base privada.
- Smoke real previo: API en `127.0.0.1:8768`, frontend en `127.0.0.1:5173`, health listo y cuatro recorridos de navegador aprobados.
- `scripts/stop_demo.ps1` detuvo los procesos propios; no quedaron listeners OpsBridge en 5173/8768.

## 4. Evidencia visual

- Dashboard escritorio: `docs/screenshots/audit-chatgpt-dashboard-desktop.png`.
- Dashboard móvil: `docs/screenshots/audit-chatgpt-dashboard-mobile.png`.
- Ticket cerrado escritorio: `docs/screenshots/audit-blockers-ticket-closed-desktop.png`.
- Ticket cerrado móvil: `docs/screenshots/audit-blockers-ticket-closed-mobile.png`.

Las capturas nuevas se generaron con datos sintéticos durante el recorrido aprobado y se inspeccionaron visualmente. No contienen contraseñas, cookies ni tokens.

## 5. Archivos funcionales modificados

- `backend/src/opsbridge/application/tickets.py`
- `backend/src/opsbridge/application/automation.py`
- `backend/src/opsbridge/presentation/http/routes/tickets.py`
- `backend/tests/test_ticket_api.py`
- `backend/tests/test_automation_api.py`
- `backend/tests/test_bootstrap.py`
- `frontend/src/api.ts`, `types.ts`, `App.tsx`, `styles.css`, `App.test.tsx`
- `frontend/e2e/core-flow.spec.ts`
- Documentación de estado, API, arquitectura, seguridad, resultados, README y guía de reclutador.

## 6. Riesgos y pendientes explícitos

- SQLite conserva el límite de un escritor efectivo y no demuestra escala empresarial.
- El catálogo tiene una sola herramienta VPN estrictamente simulada; no opera red, SSO ni cuentas reales.
- FTS5 es recuperación léxica. No se ejecutó un LLM; el estado sigue siendo `LOCAL_LLM_PENDING`.
- Python 3.11, Firefox y Safari no se ejecutaron.
- El timeline comunica truncamiento, pero todavía no ofrece navegación visual a páginas históricas posteriores.
- `waiting_approval` permanece en el dominio, pero queda cerrado en la API hasta diseñar evidencia persistida genérica.
- La licencia del repositorio sigue siendo una decisión del titular antes de publicar.

## 7. Comandos principales ejecutados

```powershell
cd <PROJECT_ROOT>\backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests
.\.venv\Scripts\python.exe -m mypy --strict src
.\.venv\Scripts\python.exe -m pip check

cd ..\frontend
pnpm typecheck
pnpm lint
pnpm test -- --run
pnpm build
pnpm audit --audit-level high
pnpm exec playwright test
```

## 8. Decisión

Los tres bloqueantes P1 reportados están corregidos y cubiertos por pruebas de aplicación, API, componente y navegador real. El candidato es **GO para revisión humana local**. Se mantiene **NO GO para publicación automática**: el titular debe revisar visualmente, decidir licencia y autorizar expresamente cualquier inicialización Git o publicación. DataTrust no fue modificado y no se creó commit, remoto ni publicación.
