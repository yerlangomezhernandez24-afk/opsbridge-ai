# Auditoría final independiente Codex — OpsBridge AI

**Fecha:** 2026-10-28  
**Candidato:** `v1.0.0-rc.1 Portfolio Local Candidate` (Python `1.0.0rc1`, npm `1.0.0-rc.1`)  
**Responsable:** Yerlan Daniel Gómez Hernández  
**Entorno:** Windows 11 x64 (`10.0.26200`), Intel Core i7-10510U (4C/8T), 11.81 GiB RAM, Intel UHD 1 GiB, 369.52 GiB libres  
**Decisión:** **GO para revisión humana local. NO GO para publicación automática o uso productivo.**

## 1. Alcance e inventario verificado

Se inspeccionaron los contratos, el estado persistente, el informe de cierre, el backend, el frontend y los artefactos de prueba. No se reconstruyó la arquitectura ni se modificó DataTrust.

| Área | Verificación real |
|---|---|
| Sesión | inicio/cierre, cookie opaca, CSRF, Origin, expiración y roles |
| Tickets | creación, listado, detalle, transición, timeline, ETag, conflicto obsoleto e idempotencia |
| Autorización | requester limitado a sus recursos; ticket ajeno no revelado; roles técnico/aprobador |
| Conocimiento | FTS5, citas, scope por rol, abstención y corpus sintético |
| Automatización | propuesta Rules, aprobación independiente, hash/caducidad/versión, simulador VPN y rechazo de replay |
| Persistencia | migraciones `0001`–`0005`, transacciones, eventos y SQLite real |
| UI | login, dashboard, tickets, detalle, modal, conocimiento, aprobaciones, analítica y configuración |

## 2. Defectos encontrados y corregidos

1. El modal de creación carecía de ciclo de foco y restauración explícita. Se añadió foco inicial, Tab/Shift+Tab circular, Escape, descripción accesible y retorno al disparador; componente y navegador real lo verifican.
2. La pantalla de aprobaciones mostraba un éxito genérico. Ahora presenta el estado y contador devueltos por el simulador, con región `status`.
3. El E2E de automatización asumía siempre `reset #1` y falló legítimamente al repetirse sobre una base preservada. Se cambió para aceptar cualquier contador positivo y se mantiene el rechazo explícito de una segunda ejecución.
4. La evaluación documental era demasiado pequeña. Se amplió de 6 a 13 casos sintéticos, con categorías adicionales, permisos, abstención y contenido adversarial.
5. La documentación conservaba cifras y pendientes obsoletos. Se sincronizaron estado, resultados, README e issues.

No se encontraron defectos P0/P1 abiertos después de las correcciones. Los P2 restantes están en `docs/ISSUES_PENDIENTES.md`.

## 3. Resultados exactos de calidad

| Comando / control | Resultado |
|---|---|
| `python -m ruff format --check .` | 96 archivos ya formateados |
| `python -m ruff check .` | aprobado |
| `python -m mypy src tests` | aprobado, 88 archivos |
| `python -m pytest -q` | **211 aprobadas**, 45.35 s |
| `python -m pip check` | sin dependencias rotas |
| `pnpm typecheck` | aprobado |
| `pnpm lint` | aprobado, cero warnings |
| `pnpm test` | **4 aprobadas**, 1 archivo, 13.56 s |
| `pnpm build` | aprobado; JS 673.51 kB minificado / 201.03 kB gzip; warning P2 de chunk >500 kB |
| `pnpm test:e2e` final | **4 aprobadas**, Chrome, 47.0 s |
| `pnpm audit --audit-level low` | sin vulnerabilidades conocidas |
| `pip-audit 2.10.1 --local` | sin vulnerabilidades conocidas; el paquete local `opsbridge-ai` se omite por no existir en PyPI |
| instalación limpia | editable bajo `requirements.lock`, `pip check` limpio, **211 aprobadas** en 42.34 s |
| smoke HTTP | `/health/live`, `/health/ready`, `/openapi.json` y web: HTTP 200 |

La primera repetición E2E de cierre produjo 3 aprobadas y 1 fallida por la suposición fija `reset #1`. Tras corregir la prueba, la suite completa quedó en 4/4; el fallo no se ocultó ni se debilitó la comprobación de replay.

## 4. Migraciones y transacciones

Sobre `backend/var/audit_migration_20261028.db`, base desechable ignorada:

- `alembic upgrade head`: creó `0001` a `0005`.
- `alembic current`: `0005_governed_automation (head)`.
- `alembic downgrade -1`: regresó a `0004_knowledge_fts`.
- `alembic upgrade head`: reaplicó `0005`.
- `alembic check`: `No new upgrade operations detected`.

Las pruebas backend cubren rollback, atomicidad, eventos, actualizaciones condicionales y conflictos optimistas. El E2E final verificó dos sesiones técnicas contra la misma versión: la primera transición se confirmó y la segunda mostró conflicto sin sobrescritura silenciosa.

## 5. Evaluación de seguridad

- Controles verificados: sesión opaca server-side, Argon2id, CSRF, Origin exacto, RBAC, autorización por recurso, 404 uniforme contra IDOR/BOLA, ETag/If-Match e idempotencia persistente.
- Los recorridos negativos comprobaron ticket ajeno, CSRF ausente, ETag obsoleto, decisión repetida, ejecución repetida y cambio de payload con la misma clave idempotente.
- `.env`, bases, logs, entornos, builds y reportes de navegador están ignorados. No hay credenciales predeterminadas; las cuentas de auditoría fueron sintéticas y locales.
- La búsqueda dirigida no encontró claves cloud ni claves privadas. Las coincidencias de contraseña corresponden a contratos, fixtures sintéticos y pruebas de redacción de logs.
- `pip-audit` encontró inicialmente avisos aplicables únicamente al `pip 25.0.1` embebido en el entorno desechable. Se actualizó a `pip 26.2.2` —igual que el script de instalación— y la repetición quedó limpia.
- Limitaciones: no existe certificación externa, pentest, Firefox/Safari, Python 3.11 ni prueba de carga empresarial; SQLite sigue siendo single-writer.

## 6. Evaluación visual y accesibilidad

La aplicación se inspeccionó en navegador Chromium real mediante accesibilidad y captura, además de Playwright. La jerarquía, contraste, espaciado, navegación, tablas, formularios, estados vacíos/error/carga y responsive resultaron coherentes con la identidad OpsBridge.

- Cinco viewports: 360×800, 390×844, 768×1024, 1366×768 y 1920×1080, sin overflow horizontal en el detalle.
- axe: cero violaciones `serious`/`critical` en el recorrido probado.
- Modal: foco inicial, ciclo de teclado, Escape y restauración comprobados.
- Dashboard, analítica e indicadores consumen datos de API; no se presentan métricas inventadas.
- No se afirma conformidad WCAG 2.2 AA completa: faltan auditoría manual especializada y navegadores alternos.

Capturas reales actualizadas:

- `docs/screenshots/phase3-overview-desktop.png`
- `docs/screenshots/phase3-ticket-detail-desktop.png`
- `docs/screenshots/phase3-ticket-detail-mobile.png`
- `docs/screenshots/phase3-technician-workspace.png`
- `docs/screenshots/phase4-knowledge-desktop.png`
- `docs/screenshots/phase4-approval-desktop.png`
- `docs/screenshots/phase4-execution-desktop.png`

## 7. Evaluación de IA y automatización

No se ejecutó ni descargó Ollama. El equipo tiene almacenamiento suficiente, pero durante la auditoría solo disponía de 1.29 GiB RAM libre, usa iGPU Intel y no tiene `ollama`, Docker, NVIDIA/CUDA ni `nvidia-smi`. Descargar un modelo sin margen operativo razonable habría sido contrario al alcance. El estado permanece **`LOCAL_LLM_PENDING`**.

La capacidad implementada no se presenta como LLM:

- Rules: política determinista y allowlist.
- Retrieval: SQLite FTS5 léxico con citas y permisos.
- Dataset `retrieval_v1`: 13 casos; 9 contestables y 4 de abstención.
- Métricas reproducidas: recall@3 **1.0**, precision@3 **1.0**, exactitud de abstención **1.0**.
- Automatización: una única herramienta VPN sintética; aprobación humana separada y ejecución exactamente una vez.

Estas métricas pertenecen a un corpus pequeño y sintético; no demuestran generalización, razonamiento generativo ni precisión empresarial.

## 8. Versiones comprobadas

- Python 3.12.14; pip 26.2.2.
- FastAPI 0.162.0; SQLAlchemy 2.1.6; Alembic 1.20.1; pytest 9.2.0; Ruff 0.17.3; mypy 2.4.0.
- Node.js 24.22.1; pnpm 11.25.0; React 19.3.1; TypeScript 6.0.3; Vite 8.3.5; Playwright 1.64.1.
- Git 2.53.0 disponible, pero no existe repositorio Git en el directorio y no se creó ninguno.

Python 3.11 figura en metadata, pero no fue ejecutado y permanece pendiente.

## 9. Inicio exacto en Windows

```powershell
cd <PROJECT_ROOT>\backend
.\scripts\setup.ps1
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m opsbridge.cli.seed_knowledge

cd ..\frontend
pnpm install --frozen-lockfile

cd ..
.\scripts\start_demo.ps1 -BackendPort 8768
```

Crear previamente requester, technician y approver con `backend\scripts\create-user.ps1`; la contraseña se introduce sin eco. Abrir `http://127.0.0.1:5173` y OpenAPI en `http://127.0.0.1:8768/docs`. Detener de forma controlada:

```powershell
cd <PROJECT_ROOT>
.\scripts\stop_demo.ps1
```

## 10. Limitaciones, pendientes y decisión

Permanecen: elección de licencia, revisión humana del contenido, Python 3.11, Firefox/Safari, LLM local, prueba HTTP específica de bloqueo SQLite para endpoints nuevos, catálogo limitado a VPN y escala local SQLite. El cierre posterior dividió el bundle, midió duración real y uniformó la traducción de errores.

**GO para someter el candidato a revisión humana local.** Los recorridos principales, controles negativos, build, instalación limpia, migraciones y auditorías de dependencias pasaron.

**NO GO para publicar automáticamente o declarar producción.** El titular debe revisar claims/capturas, elegir licencia, decidir los P2 aceptables y comprobar que no se incluyan bases, `.env`, artefactos o credenciales antes de inicializar Git. Esta auditoría no creó commits, remotos ni publicación.

## 11. Archivos principales modificados

- `frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `frontend/e2e/core-flow.spec.ts`.
- `backend/data/evaluation/retrieval_v1.json`, `backend/tests/test_knowledge_api.py`.
- `docs/PROJECT_STATE.md`, `docs/ISSUES_PENDIENTES.md`, este informe y documentación de resultados/cierre.
- `README.md` y `README.en.md`.

