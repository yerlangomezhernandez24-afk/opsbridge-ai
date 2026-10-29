# Caso empresarial hipotético

## Problema

Un equipo de soporte puede recibir solicitudes por canales dispersos, perder contexto y ejecutar acciones con evidencia o autorización inconsistentes. Este escenario es hipotético: OpsBridge no afirma clientes, tiempos ahorrados ni uso productivo.

## Propuesta

OpsBridge reúne ticket, estado, timeline, documentación citada y una propuesta accionable. La política del servidor —no el texto del ticket ni un modelo— decide qué herramienta existe. Un aprobador distinto confirma una propuesta ligada a versión, argumentos, hash y caducidad; después el técnico consume la aprobación una sola vez en un simulador.

## Responsabilidades

- Solicitante: describe y consulta sus incidentes.
- Técnico: clasifica, investiga, cambia estados y propone una acción permitida.
- Aprobador: revisa riesgo y evidencia; aprueba o rechaza sin ejecutar.
- Sistema: aplica RBAC, transacción, concurrencia, trazabilidad y abstención.

## Riesgos

Datos insuficientes, documentos maliciosos, permisos incorrectos, decisiones obsoletas, doble ejecución, indisponibilidad de SQLite y sobreconfianza en resultados sintéticos. Los controles actuales reducen esos riesgos en la demo; no demuestran cumplimiento regulatorio ni operación empresarial.

## Beneficio potencial por comprobar

Un flujo centralizado podría mejorar consistencia, explicabilidad y revisión humana. Para validarlo se necesitarían usuarios reales autorizados, tareas representativas, métricas definidas antes del piloto y comparación controlada de tasa de resolución, retrabajo, calidad de evidencia y carga del aprobador. No se asignan cifras sin ese estudio.

## Plan de evaluación

1. Taller de amenazas y permisos con responsables.
2. Corpus aprobado y conjunto de incidentes anonimizado o sintético.
3. Piloto aislado sin acciones reales.
4. Métricas de utilidad, falsos positivos, abstención y decisiones revertidas.
5. Go/no-go humano antes de cualquier integración empresarial.
