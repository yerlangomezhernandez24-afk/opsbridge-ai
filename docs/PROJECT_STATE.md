# Estado del proyecto — OpsBridge AI

**Última actualización:** 2026-10-29  
**Fase actual:** publicación GitHub autorizada; preflight, MIT y CI preparados  
**Próxima fase:** commit inicial auténtico, creación pública, CI remota y etiqueta RC  
**Ruta de trabajo:** raíz local del repositorio (`<PROJECT_ROOT>` en la documentación portable)

## 1. Estado verificable

El sistema dispone de backend FastAPI, persistencia SQLAlchemy/Alembic, autenticación local, API REST, frontend React, recuperación léxica FTS5 con citas y automatización VPN sintética gobernada. Autorización por recurso, CSRF, Origin, ETag, idempotencia, aprobación independiente y ejecución única están conectados a SQLite real.

Resultado vigente tras las correcciones finales:

- **GO técnico para revisión humana local; NO GO para publicación automática o producción.**
- Ruff/formato, mypy estricto, `pip check` y **215 pruebas backend** aprobados.
- Frontend: TypeScript, ESLint, build, **7 pruebas de componente** y **4 E2E Chrome** aprobados.
- Instalación limpia bajo `requirements.lock`: `pip check` y 215 pruebas aprobados.
- `pip-audit 2.10.1` y `pnpm audit`: sin vulnerabilidades conocidas en dependencias publicadas; el paquete editable local se omite en PyPI.
- Evaluación documental: **13 casos**, recall@3 1.0, precision@3 1.0 y abstención 1.0.
- Ollama/Docker/NVIDIA no disponibles; 11.81 GiB RAM con 1.29 GiB libre e iGPU Intel. Se conserva `LOCAL_LLM_PENDING` y no se descargó un modelo.
- Informe vigente: `docs/CIERRE_AUDITORIA_CHATGPT.md`.

Resultado de Fase 2.3B:

- **GO** en Windows 11 x64 con Python 3.12.14.
- Línea base 2.3A: 187 pruebas aprobadas.
- Cierre: Ruff y formato aprobados; mypy estricto aprobado (78 archivos); pytest **203 aprobadas, 0 fallidas**; `pip check` limpio.
- Uvicorn real en loopback: health y OpenAPI verificados; proceso detenido.
- Alembic: downgrade `0003 -> 0002`, upgrade, `check` y head aprobados en base desechable.
- Prueba HTTP VPN reproducible aprobada con IDOR, replay, ETag obsoleto y timeline.
- No se modificó DataTrust, no se creó Git y no se publicó contenido.

Informe: `docs/FASE_2_3B_TICKETS_API.md`. ADR: `docs/adr/ADR-003-ticket-api-idempotency.md`.

## 2. API implementada

| Ruta | Control principal |
|---|---|
| `POST /api/v1/tickets` | S/T; sesión, Origin, CSRF, Idempotency-Key |
| `GET /api/v1/tickets` | S propios en SQL; T/A todos; filtros/cursor |
| `GET /api/v1/tickets/{id}` | S propietario; T/A; ETag |
| `PATCH /api/v1/tickets/{id}` | T autorizado; If-Match; categoría/impacto/urgencia |
| `POST /api/v1/tickets/{id}/transitions` | S propietario/T autorizado; dominio+If-Match |
| `GET /api/v1/tickets/{id}/transition-options` | Opciones y campos requeridos autorizados por servidor |
| `GET /api/v1/tickets/{id}/timeline` | Visibilidad de ticket; paginación por revisión |

## 3. Decisiones vigentes

| Decisión | Estado |
|---|---|
| Arquitectura | Monolito modular; HTTP/aplicación/dominio/ORM separados |
| Sesión | Opaca persistida, Argon2id, CSRF y Origin exacto |
| Propiedad | Requester filtrado en SQL y 404 uniforme para ticket ajeno |
| ETag | `"version"`; If-Match requerido; 428/412 diferenciados |
| Persistencia | `0001` tickets, `0002` auth, `0003` idempotencia/API, `0004` FTS5, `0005` automatización gobernada |
| Idempotencia | UUID v4, usuario+operación+clave, huella, snapshot, TTL 24 h |
| Transacciones | Ticket/eventos/contador/idempotencia atómicos |
| Paginación | Orden `created_at DESC, id DESC`; máximo 100 |
| UI/recuperación/automatización | React implementado; FTS5 léxico; Rules + simulador VPN gobernado; LLM real pendiente |

## 4. Componentes principales

- `backend/src/opsbridge/application/tickets.py` y `ports/tickets.py`.
- `backend/src/opsbridge/presentation/http/routes/tickets.py`.
- `backend/src/opsbridge/infrastructure/db/idempotency_repository.py`.
- `backend/alembic/versions/0003_ticket_api_idempotency.py`.
- `backend/tests/test_ticket_api.py` y pruebas de migración/regresión.
- `docs/FASE_2_3B_TICKETS_API.md` y `docs/adr/ADR-003-ticket-api-idempotency.md`.

## 5. Limitaciones y riesgos

1. Python 3.11 no fue ejecutado.
2. `pip-audit` cubre dependencias publicadas, pero omite `opsbridge-ai` editable porque no existe en PyPI.
3. SQLite admite un escritor efectivo y no demuestra escala empresarial.
4. Cursores estrictos no están firmados; no son frontera de autorización y cada página reaplica scope SQL.
5. `context`, comentarios, asignación independiente, export y edición de título/descripcion no tienen soporte de dominio aprobado y no se fingieron.
6. Idempotencia se implementó para creación; transiciones usan ETag/transacción pero no Idempotency-Key.
7. Limpieza de idempotencia expirada es oportunista, no programada.
8. Los artefactos desechables ignorados de verificación local permanecen fuera de control de versiones y sin datos reales.
9. El estado `waiting_approval` permanece en el dominio para una integración futura, pero la API pública no permite entrar o salir de él hasta disponer de evidencia de aprobación persistida y verificable.

## 6. Restricciones y siguiente paso

- No ampliar a LLM, agentes, nuevas herramientas o integraciones sin autorización explícita.
- No modificar DataTrust, publicar, crear commits/remotos o usar datos reales.
- No declarar preparación productiva ni seguridad empresarial completa.

La revisión humana autorizó publicación pública bajo MIT el 2026-10-29. La publicación debe conservar `v1.0.0-rc.1`, esperar CI remota verde antes de etiquetar y nunca desplegar servicios.

## 11. Preflight de publicación GitHub 2026-10-29

- Destino autorizado: `yerlangomezhernandez24-afk/opsbridge-ai`, visibilidad pública; el preflight confirmó respuesta 404 antes de crearlo.
- Git inicializado localmente en `main`; identidad configurada como Yerlan Daniel Gómez Hernández con el correo `noreply` exacto mostrado por GitHub.
- Licencia MIT añadida; README español/inglés y README backend sincronizados; workflow `.github/workflows/ci.yml` preparado con permisos `contents: read`.
- Auditoría pública: 182 archivos candidatos, sin `.env`, bases, sesiones, tokens, entornos, `node_modules`, builds, ZIP o rutas personales.
- Regresión previa: 215 pytest, Ruff/formato, mypy estricto, `pip check`, migraciones, 7 Vitest, TypeScript, ESLint, build, `pip-audit` y `pnpm audit` aprobados.
- Informe: `docs/INFORME_PUBLICACION_GITHUB.md`. Falta completar hechos remotos después del push y verificar Actions antes de crear la etiqueta.

## 7. Sesión de culminación 2026-10-28

El responsable autorizó ejecutar secuencialmente la verificación 2.3B y las fases 3–6 mediante el prompt maestro de culminación. El preflight confirmó la ruta, los documentos, las migraciones `0001`–`0003` y la ausencia de repositorio Git local. Esta sección conserva la cronología; los gates vigentes son los de la auditoría final indicados al inicio del documento.

### Verificación 2.3B y Fase 3

- Baseline repetida: Ruff/formato/mypy/pip limpios y 203 pruebas backend aprobadas en 43.76 s.
- Prueba HTTP VPN dirigida: 1 aprobada.
- Frontend React/TypeScript/Vite implementado en `frontend/` con lock de pnpm.
- Typecheck, ESLint, build y 3 pruebas de componentes aprobados.
- Playwright Chrome: 2 E2E reales aprobadas; solicitante crea y técnico avanza ticket persistido.
- axe sin violaciones serious/critical tras corregir contraste; cinco viewports sin overflow.
- Informe: `docs/FASE_3_FRONTEND_PROFESIONAL.md`; capturas: `docs/screenshots/`.
- Estado: **WEB_GO**. Ollama no está instalado; Fase 4 comienza como `LOCAL_LLM_PENDING` sin disfrazar rules como IA.

### Fase 4 — conocimiento y automatización gobernada

- Migraciones `0004_knowledge_fts` y `0005_governed_automation` verificadas desde base vacía y con `alembic check` limpio.
- Corpus sintético de cuatro documentos; FTS5 con permisos, citas, apertura de fragmento y abstención.
- Dataset `retrieval_v1`: 13 casos tras auditoría final, recall@3 1.0, precision@3 1.0 y abstención 1.0.
- Acción VPN estrictamente sintética: propuesta rules, aprobación separada, hash/caducidad/versión y ejecución exactamente una vez.
- Regresión de Fase 4: Ruff/formato/mypy/pip limpios; **211 pruebas backend**; frontend typecheck/lint/build y 3 componentes; **3 E2E Chrome**. La auditoría final posterior elevó la cobertura a 4 componentes y 4 E2E.
- Gates: **GO_CORE**, **RAG_GO**, **AGENT_SIM_GO limitado**; **LOCAL_LLM_PENDING**.
- Informe: `docs/FASE_4_IA_AUTOMATIZACION.md`.
- Riesgos P2: corpus/evaluación pequeños, un solo simulador, auditoría sin duración medida, bundle web grande y SQLite local.

### Fase 5 — auditoría integral

- 0 P0/P1 conocidos; P2 abiertos en `docs/ISSUES_PENDIENTES.md`.
- Auditoría backend/frontend/E2E repetida; seguridad, migraciones, permisos, retrieval, concurrencia y visuales contrastados.
- En Fase 5, `pnpm audit` no encontró vulnerabilidades y `pip-audit` quedó Not Tested; la auditoría final posterior ejecutó `pip-audit 2.10.1` con resultado limpio para dependencias publicadas.
- Rendimiento local secuencial: health p95 7.84 ms; tickets p95 22.81 ms; knowledge p95 19.96 ms en dataset sintético pequeño.
- Corregidos: ignores Node/Playwright, separación Vitest/Playwright y score FTS5 no negativo.
- Informe: `docs/FASE_5_AUDITORIA_FINAL.md`. Estado: **GO condicionado para portafolio local**, no producción.

### Fase 6 — cierre de portafolio

- README español/inglés, SECURITY, arquitectura final, instalación, demo, caso empresarial, resultados y CV creados.
- Scripts raíz `start_demo.ps1` y `stop_demo.ps1` comprobados en puertos 8768/5173: migración, seed, health 200, web 200 y parada sin procesos propios persistentes.
- Entorno virtual limpio `.venv-final-verify`: instalación editable bajo lock, `pip check` y **211 pruebas aprobadas en 36.18 s**.
- Capturas reales de Knowledge, Approval y ejecución agregadas e inspeccionadas.
- Versión propuesta: **v1.0.0-rc.1 Portfolio Local Candidate**. Metadata alineada como Python `1.0.0rc1` y npm `1.0.0-rc.1`; no se creó tag/commit.
- Gates finales de Fase 6: CORE GO, UI WEB_GO, RAG_GO léxico, AGENT_SIM_GO limitado, LLM REAL PENDING, SEGURIDAD/REPRODUCIBILIDAD GO condicionado. La auditoría posterior cerró `pip-audit`; publicación continúa NO GO hasta revisión humana y licencia.
- Informe: `docs/INFORME_CIERRE_OPSBRIDGE_PORTAFOLIO.md`.
- No se creó Git, commit, remoto, publicación o integración real.

## 8. Preparación para revisión humana 2026-10-28

- Demo local iniciada en `http://127.0.0.1:5173` con API en `http://127.0.0.1:8768`; liveness, readiness y frontend respondieron HTTP 200.
- DataTrust permanece sin cambios en su puerto 8000; OpsBridge usa el puerto alternativo 8768.
- La base estándar no contiene credenciales predeterminadas. El responsable debe crear `demo.requester`, `demo.technician` y `demo.approver` mediante `backend/scripts/create-user.ps1`, introduciendo contraseñas sintéticas de forma interactiva y sin eco.
- ZIP recomendado creado fuera del proyecto: `<PROJECT_ROOT>_exports\OpsBridge_AI_v1.0.0-rc.1_human_review.zip`.
- El paquete se valida después de crearlo: cero rutas prohibidas y presencia de código, locks, informe y capturas requeridas.
- No se creó Git, commit, remoto ni publicación. No se añadieron funcionalidades.

## 9. Correcciones finales de auditoría ChatGPT 2026-10-28

- Dashboard/Analítica consumen agregados SQL de todo el alcance autorizado mediante `/api/v1/tickets/summary`; Tickets navega cursores en páginas de 25.
- Cobertura nueva con 112 tickets, dos solicitantes, técnico y filtro; regresión backend final: **212 passed**.
- Frontend final: TypeScript, ESLint, **5 componentes**, build dividido y `pnpm audit` aprobados; **4 E2E Chrome** aprobados en 35,7 s.
- Gráficos verificados contra respuesta API después de animación y nuevas capturas escritorio/móvil en `docs/screenshots/audit-chatgpt-dashboard-*.png`.
- Versión alineada: humano `v1.0.0-rc.1`, Python `1.0.0rc1`, npm `1.0.0-rc.1`.
- Automation registra duración real; Knowledge/Automation traducen fallos SQLite; documentación portable sin rutas personales.

## 10. Cierre de bloqueantes de auditoría independiente 2026-10-29

- La UI dejó de mantener una matriz de transiciones propia: consume `GET /tickets/{id}/transition-options` y solicita los campos obligatorios devueltos por el servidor.
- Se eliminaron del contrato HTTP las afirmaciones cliente `approval_resolved` y `approval_reference`. El flujo genérico `waiting_approval` queda cerrado hasta existir evidencia persistida verificable.
- El reset VPN solo puede proponerse, aprobarse y ejecutarse mientras el ticket está `in_progress`, conserva la versión y está asignado al técnico proponente; cancelar o modificar el ticket invalida la propuesta sin efecto.
- La creación conserva una misma `Idempotency-Key` durante reintentos del mismo formulario. Timeline informa explícitamente cuando solo muestra los primeros 100 eventos.
- Evidencia final: 215 pruebas backend, 7 pruebas de componente, 4 E2E Chrome, Ruff, mypy estricto, TypeScript, ESLint, build, `pip check`, `pip-audit` y `pnpm audit` aprobados.
- Migraciones `0001`–`0005`: upgrade desde vacío, downgrade a base, re-upgrade y `alembic check` aprobados en base desechable.
- Capturas nuevas: `docs/screenshots/audit-blockers-ticket-closed-desktop.png` y `audit-blockers-ticket-closed-mobile.png`.
- Informe vigente: `docs/CIERRE_HALLAZGOS_AUDITORIA_FINAL.md`.
- Instalación limpia Python 3.12.14: paquete 1.0.0rc1, `pip check` y 212 pruebas aprobadas. Alembic upgrade/downgrade/re-upgrade hasta `0005` aprobado.
- `pip-audit` y `pnpm audit`: sin vulnerabilidades conocidas; el paquete editable local no es auditable en PyPI.
- El script de demo detecta puertos ocupados y espera readiness. DataTrust no fue modificado ni detenido cuando se observó en 8000; OpsBridge se comprobó en 8768/5173 y todos sus procesos fueron detenidos.
- Estado: **GO para revisión humana**, no producción ni publicación automática. Informe: `docs/CIERRE_AUDITORIA_CHATGPT.md`.

## 10. Paquete FINAL_REVIEW 2026-10-28

- Correcciones críticas reconfirmadas mediante inspección de código, versiones, 2 pruebas backend dirigidas y 5 pruebas de componente; no se repitieron suites completas sin cambios funcionales.
- Paquete externo solicitado: `OpsBridge_AI_v1.0.0-rc.1_FINAL_REVIEW.zip`, con 176 archivos del proyecto.
- Incluye fuente, pruebas, migraciones, locks, scripts, documentación y capturas reales; conserva `.env.example` sin secretos.
- Excluye `.env` reales, bases/sesiones, `var`, entornos virtuales, `node_modules`, builds, caches, reportes Playwright y temporales.
- El SHA-256 se calcula sobre el ZIP final y se entrega fuera de este archivo para evitar una referencia circular al propio contenido.
- DataTrust no se modificó. No se creó Git, commit, remoto ni publicación.
