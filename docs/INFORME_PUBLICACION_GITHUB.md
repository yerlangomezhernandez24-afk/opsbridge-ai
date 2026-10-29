# Informe de publicación en GitHub

**Proyecto:** OpsBridge AI `v1.0.0-rc.1`  
**Propietario:** Yerlan Daniel Gómez Hernández  
**Fecha:** 2026-10-29  
**Destino autorizado:** `yerlangomezhernandez24-afk/opsbridge-ai` público

## Estado previo a publicación

- Fuente utilizada: directorio de trabajo real, no el ZIP de auditoría.
- Repositorio objetivo: no existente al preflight público (respuesta 404).
- Licencia: MIT, copyright 2026 Yerlan Daniel Gómez Hernández.
- Versión: humana `v1.0.0-rc.1`, Python `1.0.0rc1`, npm `1.0.0-rc.1`.
- Auditoría del conjunto público: sin `.env`, bases, sesiones, cookies, tokens, entornos virtuales, `node_modules`, builds, cachés, ZIP o rutas privadas del propietario.
- Capacidades limitadas honestamente: FTS5 léxico, Rules y VPN simulada; `LOCAL_LLM_PENDING`; no producción.

## Validación local vigente

- Backend: 215 pruebas en 42.03 s; Ruff, formato y mypy estricto aprobados; `pip check` limpio.
- Frontend: TypeScript, ESLint, 7 pruebas Vitest en 6.43 s y build en 1.39 s aprobados.
- Navegador: 4 recorridos Playwright Chrome aprobados localmente.
- Dependencias: `pip-audit` y `pnpm audit --audit-level high` sin vulnerabilidades conocidas en paquetes publicados.
- Migraciones: vacío → `0005`, downgrade, re-upgrade y `alembic check` aprobados en base desechable.

## CI preparada

`.github/workflows/ci.yml` usa permisos `contents: read`. El job backend ejecuta Python 3.12, instalación bajo lock, Ruff, mypy, pytest y migraciones. El job frontend ejecuta pnpm 11.25.0/Node 24, instalación congelada, TypeScript, ESLint, Vitest y build. Playwright no se ejecuta remotamente porque las cuentas se crean de forma interactiva y no se publican contraseñas sintéticas como secretos de CI.

## Resultado remoto

Pendiente hasta crear el repositorio, publicar `main` y observar GitHub Actions. Este apartado debe actualizarse exclusivamente con URLs, SHA y estados realmente verificados.

## Checklist

- [x] Código, pruebas, migraciones, scripts, documentación y capturas seleccionados.
- [x] MIT añadida y versiones alineadas.
- [x] README español/inglés y backend sincronizados con el alcance real.
- [x] Workflow CI con permisos mínimos.
- [ ] Cuenta GitHub autenticada confirmada como `yerlangomezhernandez24-afk`.
- [ ] Repositorio público creado y `main` publicada.
- [ ] CI remota concluida con éxito.
- [ ] Etiqueta anotada `v1.0.0-rc.1` publicada sobre el commit verificado.
- [ ] Topics, licencia, rama y visibilidad comprobados externamente.
