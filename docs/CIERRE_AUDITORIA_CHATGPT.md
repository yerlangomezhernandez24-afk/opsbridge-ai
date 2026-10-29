# Cierre de auditoría ChatGPT — OpsBridge AI v1.0.0-rc.1

**Fecha:** 2026-10-28  
**Decisión:** **GO para revisión humana y publicación posterior condicionada a autorización del responsable.** No es GO de producción. No se publicó, no se creó Git/commit/remoto y DataTrust no fue modificado.

## Hallazgos resueltos

1. **Indicadores parciales.** El dashboard y Analítica dejaron de agregar los primeros 100 tickets. `GET /api/v1/tickets/summary` calcula total y agrupaciones por estado, prioridad, categoría y día directamente en SQL, aplicando el mismo alcance por rol y filtros que la lista. El solicitante solo agrega sus tickets; técnico y aprobador agregan el alcance autorizado completo.
2. **Paginación ignorada.** Tickets usa páginas de 25, conserva los cursores opacos entregados por la API y ofrece Anterior/Siguiente con estados deshabilitados correctos.
3. **Versiones divergentes.** La versión humana es `v1.0.0-rc.1`, la distribución Python usa PEP 440 `1.0.0rc1` y npm usa `1.0.0-rc.1`.
4. **Bundle monolítico.** Recharts se carga de forma diferida. El bundle principal pasó de aproximadamente 673,5 kB minificados / 201 kB gzip a 301,61 kB / 95,21 kB. El chunk opcional de gráficos mide 374,56 kB / 107,23 kB gzip.
5. **Duración ficticia.** Los registros `tool_audit.duration_ms` se miden con reloj monotónico de alta resolución y se redondean hacia arriba a milisegundos; las pruebas exigen valores mayores o iguales a 1.
6. **Errores SQLite dispares.** Knowledge y Automation traducen `OperationalError` y `SQLAlchemyError` a errores de infraestructura controlados; el manejador HTTP existente conserva la respuesta diferenciada de bloqueo temporal con `Retry-After` y no filtra SQL ni rutas.
7. **Rutas no portables.** Las instrucciones públicas usan `<PROJECT_ROOT>` o rutas relativas. Las rutas absolutas quedan fuera de la documentación portable.
8. **Arranque engañoso por puerto ocupado.** `start_demo.ps1` ahora valida ambos puertos antes de iniciar, no reemplaza procesos ajenos, espera readiness hasta 10 segundos y permite elegir una base local por nombre seguro. Durante la auditoría DataTrust fue observado en 8000; no se modificó ni detuvo, y OpsBridge se verificó en 8768.

## Evidencia de paginación y métricas

- Prueba backend con **112 tickets**: 105 del solicitante propietario y 7 de otro solicitante.
- Primera página del propietario: 100; `has_more=true`; segunda: 5; `has_more=false`.
- Resumen propietario: 105; filtro `network.vpn`: 53; combinación `status=new`, `priority=p3` y texto: 10; segundo solicitante: 7; técnico: 112.
- Prueba de componente recorre `next_cursor=opaque-next` y vuelve a la página anterior.
- En Chrome real el resumen API devolvió 9 y el primer KPI mostró 9. Tras esperar 1,2 segundos, al menos una barra tuvo altura SVG positiva y el donut produjo exactamente dos sectores, iguales a las dos prioridades con conteo positivo. No se alteraron valores para la captura.

Capturas nuevas:

- `docs/screenshots/audit-chatgpt-dashboard-desktop.png`
- `docs/screenshots/audit-chatgpt-dashboard-mobile.png`

## Resultados reales

| Comprobación | Resultado |
|---|---|
| pytest completo, entorno principal | **212 passed**, 33,51 s |
| pytest, entorno virtual limpio | **212 passed**, 38,71 s |
| Ruff check / format | aprobado; 88 archivos formateados |
| mypy `--strict` | aprobado; 63 archivos fuente |
| `pip check` | sin requisitos rotos |
| `pip-audit --local` | sin vulnerabilidades conocidas; paquete local `opsbridge-ai 1.0.0rc1` omitido por no existir en PyPI |
| TypeScript | aprobado |
| ESLint | aprobado |
| Vitest | **5 passed** |
| Build Vite | aprobado; tamaños indicados arriba |
| `pnpm audit --prod` | sin vulnerabilidades conocidas |
| Playwright Chrome | **4 passed**, 35,7 s |
| Alembic base vacía | upgrade a 0005, downgrade a base, re-upgrade a 0005 aprobados |
| Smoke HTTP | `/health/ready` respondió `ready` en 127.0.0.1:8768 |

Hubo dos intentos E2E iniciales de cuatro fallos cada uno porque el proxy apuntaba al puerto 8000 ocupado por DataTrust; devolvía 404 de otro servicio. El defecto de arranque se corrigió con detección previa de puertos. La repetición aislada en 8768 aprobó 4/4. Una comprobación HTTP inmediata anterior a la espera de readiness también falló por carrera de arranque; el script ahora espera readiness y la repetición aprobó.

## Seguridad

- Sin secretos o contraseñas en fuente, documentación o capturas.
- Cookies opacas, CSRF, Origin exacto, RBAC, autorización por recurso, ETag e idempotencia conservados.
- Las métricas respetan el alcance de autorización y no devuelven identificadores personales.
- Los artefactos temporales de Playwright no forman parte del ZIP/repo por `.gitignore`; la búsqueda posterior no encontró la contraseña sintética usada mediante variable de entorno.
- El catálogo VPN continúa limitado a `DEMO-VPN-NNN`; solo cambia estado sintético local y mantiene aprobación independiente.

## Archivos creados y modificados

- Backend: puertos de tickets, servicio, repositorio SQLAlchemy, rutas HTTP, Automation, Knowledge, versión del paquete y pruebas de bootstrap/tickets/automatización.
- Frontend: `App.tsx`, `api.ts`, `types.ts`, `styles.css`, pruebas de componentes, Playwright y nuevo `OperationalCharts.tsx`.
- Operación: `scripts/start_demo.ps1`.
- Documentación: README ES/EN, API, arquitectura, instalación, recruiter, resultados, estado del proyecto, auditoría anterior y este informe.

## Pendientes y límites explícitos

- SQLite es adecuado para la demo local de un nodo, no para carga empresarial multiusuario masiva. PostgreSQL sigue siendo la evolución prevista.
- FTS5 es recuperación léxica, no IA generativa. Ollama no fue ejecutado ni verificado: `LOCAL_LLM_PENDING`.
- El simulador VPN no integra red, SSO ni equipos reales.
- Python 3.11, Firefox y Safari permanecen sin ejecución real.
- El chunk de gráficos sigue siendo grande aunque ya no penaliza la carga inicial; una sustitución de librería solo se justifica con presupuesto de rendimiento medido.
- El informe externo `OPSBRIDGE_AUDITORIA_INDEPENDIENTE_CHATGPT.md` no estaba disponible en la raíz; se trabajó contra los hallazgos enumerados en la solicitud.

## Comandos principales ejecutados

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests
.\.venv\Scripts\python.exe -m mypy --strict src
.\.venv\Scripts\python.exe -m pip check
.\.venv-final-verify\Scripts\pip-audit.exe --local
pnpm exec tsc -b
pnpm exec eslint .
pnpm test -- --run
pnpm run build
pnpm audit --prod
pnpm exec playwright test
python -m alembic upgrade head
python -m alembic downgrade base
.\scripts\start_demo.ps1 -BackendPort 8768
.\scripts\stop_demo.ps1
```

## Recomendación de release

Autorizar revisión humana sobre `v1.0.0-rc.1`, comprobar manualmente el recorrido de los tres roles y solo después decidir licencia, inicialización Git y publicación. No promover todavía a `v1.0.0` definitiva ni iniciar nuevas funcionalidades.
