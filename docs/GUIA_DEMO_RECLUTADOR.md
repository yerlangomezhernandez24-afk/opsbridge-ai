# Demo para reclutador — 3 a 5 minutos

## Preparación

Use una base local limpia, cree tres cuentas interactivas y arranque con `scripts/start_demo.ps1 -BackendPort 8768` en el equipo auditado (8000 pertenece a DataTrust). Todos los nombres e incidentes deben ser ficticios. Mantenga visible que el modo es **Rules · Sin LLM**.

## Recorrido

1. **Solicitante (45 s).** Inicie sesión, muestre el dashboard y cree “VPN sintética bloqueada” con descripción suficiente. Abra detalle y señale clave pública, prioridad calculada, versión y timeline persistido.
2. **Técnico (60 s).** Cierre sesión, ingrese como técnico, abra el ticket, seleccione “Clasificado”, confirme, seleccione “En progreso” y confirme. En Conocimiento busque “vpn sesión bloqueada”; abra/lea la cita `KB-VPN-001`. Explique que FTS5 se abstiene sin evidencia y filtra documentos por rol.
3. **Propuesta (30 s).** En detalle pulse “Proponer reset sintético”. Aclare: Rules propone; no hubo inferencia LLM ni efecto todavía. La identidad `DEMO-VPN-001` está en allowlist.
4. **Aprobador (45 s).** Cambie a una cuenta aprobadora. En Aprobaciones muestre herramienta, versión, caducidad y huella; apruebe. Explique separación de funciones y que la aprobación no es reutilizable.
5. **Ejecución (45 s).** Regrese al técnico y ejecute el simulador. Muestre estado `executed`; un segundo intento se rechaza. Cierre con Analítica y Settings, aclarando que los KPI provienen solo de datos demo.

## Qué decir con precisión

- “La recuperación léxica obtuvo 1.0 en recall@3/precision@3/abstención sobre 13 casos sintéticos.”
- “No ejecuté un LLM local; la UI reporta `LOCAL_LLM_PENDING`.”
- “El efecto es un registro SQLite del simulador VPN; no toca SSO, red o equipos.”
- “215 pruebas backend, siete pruebas de componentes y cuatro E2E Chrome pasaron al corte; Python 3.11 y Safari/Firefox quedan pendientes.”
- “La lista navega con cursor y los KPI se calculan sobre todo el alcance autorizado, no sobre los primeros 100 registros.”

## Checklist PASS/FAIL humano

- [ ] Login/logout funcionan para los tres roles y no se muestra ninguna contraseña.
- [ ] Dashboard, tickets, detalle, conocimiento y aprobaciones cargan sin errores de consola.
- [ ] La cita corresponde a un fragmento real; una consulta inexistente se abstiene.
- [ ] Solicitante no puede proponer; técnico no puede aprobar; aprobador no ejecuta.
- [ ] La ejecución dice simulada, sucede una vez y el segundo intento falla.
- [ ] 360 px y escritorio no presentan overflow global o botones cortados.
- [ ] El modo LLM aparece pendiente, no completado.
- [ ] Los servidores se apagan con `scripts/stop_demo.ps1`.

Capturas de referencia están en `docs/screenshots/`; no contienen cookies ni contraseñas.
