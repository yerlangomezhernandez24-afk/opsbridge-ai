# Resultados verificados

**Corte:** 2026-10-29. Evidencia local, no certificación independiente.

| Capacidad | Resultado | Evidencia |
|---|---|---|
| Tickets, timeline, paginación y agregados | Verificado | 215 pruebas backend; cobertura con 112 tickets, roles/filtros; opciones de transición server-side y truncamiento explícito |
| Sesión/RBAC/CSRF/IDOR | Verificado local | pruebas auth/API y auditoría Fase 5 |
| Migraciones | Verificado | base vacía, upgrade/downgrade/re-upgrade/check hasta 0005 |
| UI responsive y gráficos | Verificado Chrome | 5 viewports, axe serious/critical 0; KPI/API y geometría SVG comprobados tras animación |
| FTS5 con citas | RAG_GO léxico | 13 casos; recall@3 1.0; precision@3 1.0; abstención 1.0 |
| Propuesta/aprobación | AGENT_SIM_GO limitado | hash, caducidad, roles, versión, estado/asignación vigentes y una ejecución |
| LLM local | No verificado | Ollama ausente; `LOCAL_LLM_PENDING` |
| Dependencias | Verificado con límite | `pip check`, `pnpm audit` y `pip-audit` sin vulnerabilidades conocidas; `opsbridge-ai 1.0.0rc1` editable omitido por no existir en PyPI |
| Publicación | No realizada | no Git local, commit, remoto o GitHub |

Versiones: OpsBridge Python 1.0.0rc1 / npm 1.0.0-rc.1, Python 3.12.14, FastAPI 0.162.0, SQLAlchemy 2.1.6, Alembic 1.20.1, SQLite 3.53.1, Node 24.22.1, pnpm 11.25.0, React 19.3.1, Vite 8.3.5.

Rendimiento secuencial local en dataset pequeño: p95 health 7.84 ms, tickets 22.81 ms, knowledge 19.96 ms. No es SLA ni prueba de carga.

Informes fuente: `FASE_3_FRONTEND_PROFESIONAL.md`, `FASE_4_IA_AUTOMATIZACION.md`, `FASE_5_AUDITORIA_FINAL.md`, `CIERRE_HALLAZGOS_AUDITORIA_FINAL.md` e `ISSUES_PENDIENTES.md`.
