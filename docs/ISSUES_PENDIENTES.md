# Issues pendientes

**Corte:** 2026-10-28. No hay P0/P1 conocidos después de la auditoría local.

| ID | Prioridad | Estado | Descripción / criterio de cierre |
|---|---|---|---|
| OPS-P2-001 | P2 | Cerrado 2026-10-28 | Recharts separado por carga diferida. Principal 301,61 kB / 95,21 kB gzip; chunk de gráficos 374,56 kB / 107,23 kB gzip. |
| OPS-P2-002 | P2 | Cerrado 2026-10-28 | `pip-audit 2.10.1` ejecutado en entorno desechable: tras actualizar el `pip` embebido de 25.0.1 a 26.2.2, no encontró vulnerabilidades conocidas. El paquete editable local se omite porque no existe en PyPI. |
| OPS-P2-003 | P2 | Abierto | Python 3.11 no está instalado; compatibilidad declarada por metadata pero no ejecutada. |
| OPS-P2-004 | P2 | Abierto | Firefox y Safari no fueron probados. Safari no está disponible en Windows; añadir Firefox Playwright cuando el binario esté disponible. |
| OPS-P2-005 | P2 | Abierto | LLM local/Ollama no disponible. Requiere autorización de descarga, adaptador, contrato y evaluación; no bloquear el modo Rules/FTS5. |
| OPS-P2-006 | P2 | Abierto | Catálogo de simulación limitado a VPN. Software, hardware y acceso, así como orquestación multi-paso, no están implementados. |
| OPS-P2-007 | P2 | Cerrado 2026-10-28 | `tool_audit.duration_ms` usa reloj monotónico medido y pruebas exigen duración positiva. |
| OPS-P2-008 | P2 | Abierto | Conocimiento y automatización acceden a ORM desde aplicación. Extraer puertos/adaptadores si crece el módulo; hoy el alcance es local y probado. |
| OPS-P2-009 | P2 | Abierto | SQLite tiene un escritor efectivo y no valida escala multiusuario empresarial. Mantener claim de demo local. |
| OPS-P2-010 | P2 | Parcial | Knowledge y Automation traducen uniformemente fallos SQLAlchemy y bloqueo SQLite al manejador HTTP seguro. Sigue pendiente una prueba HTTP específica de bloqueo para ambos módulos. |
| OPS-P2-011 | P2 | Cerrado 2026-10-28 | Modal con foco inicial, ciclo Tab/Shift+Tab, Escape y restauración al disparador; prueba de componente y recorrido Playwright aprobados. Esto no equivale por sí solo a certificación WCAG 2.2 AA. |

## Corregidos durante Fase 5

- `OPS-P2-F01`: artefactos `node_modules`, Playwright, Vite y coverage agregados al `.gitignore`.
- `OPS-P2-F02`: relevancia FTS5 convertida a magnitud no negativa para no mostrar semántica BM25 interna confusa; cinco pruebas de conocimiento aprobadas.
- `OPS-P2-F03`: Vitest restringido a pruebas de componente para que no intente ejecutar specs de Playwright. Esto separa runners; no excluye E2E, que conserva su comando y pasó por separado.

## Corregidos durante auditoría final independiente

- `OPS-P2-A01`: focus trap y restauración explícita del modal, con Escape y descripción accesible.
- `OPS-P2-A02`: el resultado de ejecución muestra estado y contador reales del simulador.
- `OPS-P2-A03`: el E2E dejó de asumir `reset #1`; ahora es repetible sobre una base local preservada y sigue comprobando rechazo del replay.
- `OPS-P2-A04`: dataset documental ampliado de 6 a 13 casos sintéticos, incluidos permisos, abstención y contenido adversarial.

P0 = bypass/pérdida de datos/seguridad crítica. P1 = recorrido central roto. P2 = deuda o mejora no bloqueante con limitación documentada.
