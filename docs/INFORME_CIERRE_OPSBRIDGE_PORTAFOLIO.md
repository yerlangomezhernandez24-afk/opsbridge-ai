# Informe de cierre — OpsBridge AI Portfolio Candidate

**Fecha:** 2026-10-28  
**Versión propuesta:** `v1.0.0-rc.1 Portfolio Local Candidate`  
**Estado global:** GO condicionado para revisión humana local; no listo para publicación automática ni producción.

## Gates

| Dimensión | Estado | Motivo |
|---|---|---|
| CORE BACKEND | GO | dominio, API, persistencia, migraciones, concurrencia y 212 pruebas |
| UI | WEB_GO | React real, responsive, axe/revisión visual y 4 E2E Chrome tras auditoría independiente |
| RAG | RAG_GO léxico | FTS5 citado/role-scoped, evaluación 13 casos tras auditoría independiente; no generativo |
| LLM REAL | NO GO / PENDING | Ollama/modelo no disponible ni ejecutado |
| AGENTES/APROBACIONES | AGENT_SIM_GO limitado | una herramienta VPN sintética gobernada; sin orquestador general |
| SEGURIDAD | GO condicionado | sin P0/P1 conocidos; P2 y cobertura limitada documentados |
| REPRODUCIBILIDAD | GO Python 3.12 | lockfiles, scripts y migraciones; Python 3.11 pendiente |
| LISTO PARA PUBLICAR | NO GO hasta revisión titular | falta revisión humana final y elección explícita de licencia |

## Entregables

- Backend y frontend funcionales, migraciones `0001`–`0005`, corpus/evaluación sintéticos.
- README español/inglés, SECURITY, instalación, demo, arquitectura, caso, resultados y CV.
- Scripts `start_demo.ps1` / `stop_demo.ps1`, sin credenciales predeterminadas ni cambios de política.
- Capturas reales de login/dashboard/tickets/detalle/conocimiento/aprobación/móvil.
- Auditoría y P2 en `FASE_5_AUDITORIA_FINAL.md` e `ISSUES_PENDIENTES.md`.

## Resultado técnico final

Última suite integral estable tras correcciones de auditoría: Ruff/formato/mypy/pip check aprobados; 212 pytest; frontend typecheck/lint/5 componentes/build; Playwright Chrome 4 E2E. Un entorno virtual limpio creado desde Python 3.12 instaló el proyecto bajo `requirements.lock`, pasó `pip check` y repitió 212 pruebas. `pnpm audit` y `pip-audit` no reportaron vulnerabilidades conocidas; este último omitió únicamente el paquete editable local, que no existe en PyPI.

## Riesgos que impiden v1.0.0 final

LLM no verificado, Python 3.11 y navegadores alternos no probados, catálogo de simuladores limitado y SQLite single-writer. Recharts ya está aislado en carga diferida, aunque su chunk conserva tamaño relevante. Ninguno se oculta detrás de un claim genérico de “IA completa”.

## Checklist del responsable antes de publicar

- [ ] Ejecutar instalación limpia y guía de demo en una sesión nueva.
- [ ] Confirmar apariencia y contenido en las capturas; revisar móvil y teclado.
- [x] Ejecutar `pip-audit` en entorno desechable y documentar su límite sobre el paquete editable local.
- [ ] Revisar dependencias/licencias y elegir explícitamente una licencia del repositorio.
- [ ] Confirmar que no hay `.env`, DB, logs, tokens, contraseñas, caches, builds o reportes Playwright.
- [ ] Revisar toda afirmación del README/CV y mantener “portfolio local”.
- [ ] Decidir si cerrar los P2 necesarios antes de cambiar a `v1.0.0`.
- [ ] Solo entonces inicializar Git/commit/remoto y publicar manualmente.

No se creó repositorio Git, commit, remoto ni publicación durante esta ejecución.
