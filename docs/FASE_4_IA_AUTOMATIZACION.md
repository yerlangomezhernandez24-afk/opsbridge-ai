# Fase 4 — IA aplicada y automatización gobernada

**Fecha:** 2026-10-28  
**Gate:** `GO_CORE`, `RAG_GO`, `AGENT_SIM_GO` limitado; `LOCAL_LLM_PENDING`

## Alcance comprobado

- Corpus sintético versionado para VPN, software, hardware y acceso, con permisos por rol e ingesta idempotente.
- Recuperación léxica SQLite FTS5 con citas de documento/fragmento, apertura de fuente, abstención y 404 uniforme para contenido restringido.
- Dataset ampliado en la auditoría final a 13 casos sintéticos: nueve contestables y cuatro de abstención, incluidos permisos y contenido adversarial benigno.
- Propuesta determinista `vpn_session.reset`, aprobación humana separada y ejecución exactamente una vez sobre un simulador local.
- La aprobación liga propuesta, versión del ticket, herramienta, argumentos canónicos SHA-256 y caducidad. Antes de ejecutar se revalidan actor, versión, estado, schema y hash.
- UI real para Knowledge Hub, Approval Center y estado de modos. El modo LLM se muestra como pendiente.

## Matriz de capacidades

| Modo | Implementación | Evaluación real | Estado |
|---|---|---|---|
| Rules | Política determinista, schema estricto y allowlist `DEMO-VPN-NNN` | Casos positivos, denegaciones, versión obsoleta y concurrencia | GO_CORE |
| Recuperación léxica | SQLite FTS5, scope por rol, citas y abstención | recall@3 1.0; precision@3 1.0; abstención 1.0; 13 casos tras auditoría final | RAG_GO (recuperación, no LLM) |
| LLM local | Estado contractual visible; proveedor previsto Ollama | No se ejecutó modelo ni inferencia | LOCAL_LLM_PENDING |
| Acción simulada | VPN sintética, aprobación independiente, auditoría local | Dos ejecuciones concurrentes: una 200 y una 409; un solo efecto | AGENT_SIM_GO limitado |

No se denomina RAG generativo a FTS5. No se atribuye exactitud generativa ni tool calling a un modelo no ejecutado.

## Modelo y controles

- Migración `0004_knowledge_fts`: documentos, fragmentos, roles, tabla virtual FTS5 y triggers.
- Migración `0005_governed_automation`: propuestas, ejecuciones, estado VPN sintético y auditoría.
- Herramienta con efecto: únicamente `vpn_session.reset`, sin shell, red, SSO, credenciales o equipos reales.
- Proponente: técnico. Decisor: aprobador distinto del solicitante y del proponente. Ejecutor: técnico proponente.
- Los registros de auditoría son trazabilidad local, no un ledger inmutable ni evidencia a prueba de manipulación.

## Evidencia ejecutada

| Verificación | Resultado |
|---|---|
| `python -m pytest -q` | 211 aprobadas, 0 fallidas, 41.93 s |
| `ruff format --check .` / `ruff check .` | 96 archivos formateados; sin hallazgos |
| `mypy src tests` | 88 archivos; sin hallazgos |
| `pip check` | sin dependencias rotas |
| `alembic upgrade head` | base vacía hasta `0005_governed_automation` |
| `alembic check` | sin operaciones nuevas |
| Evaluación `retrieval_v1` | 13 casos tras auditoría final; recall/precision/abstención = 1.0/1.0/1.0 |
| Frontend typecheck/lint/test/build | aprobado; 3 pruebas de componente |
| Playwright Chrome | 3 E2E, incluido recorrido KB → propuesta → aprobación → ejecución |

## Riesgos y límites

1. Ollama, Docker y un modelo local no estaban disponibles; no hubo descarga ni inferencia real.
2. El conjunto de evaluación es pequeño y sintético; sus métricas no predicen calidad empresarial.
3. Solo existe un simulador VPN y una herramienta de efecto. No se implementaron orquestador multi-paso, software, hardware o acceso.
4. SQLite permite un escritor efectivo y no representa escala multiusuario de producción.
5. La auditoría conserva actor/operación/resultado, pero `duration_ms` es todavía cero y requiere instrumentación si se usa como métrica.
6. El bundle web conserva una advertencia P2 de tamaño (~672 kB minificado, ~201 kB gzip).

## Decisión

La fase es GO para núcleo gobernado, recuperación léxica y el caso VPN sintético. La dimensión **LLM REAL no es GO** y permanece `LOCAL_LLM_PENDING`. La siguiente actividad es la auditoría independiente de Fase 5; no se amplía el catálogo de herramientas durante esa auditoría.
