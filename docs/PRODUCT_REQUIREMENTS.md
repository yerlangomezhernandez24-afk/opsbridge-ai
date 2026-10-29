# Requisitos de producto — OpsBridge AI

**Estado:** propuesta de Fase 1  
**Responsable:** Yerlan Daniel Gómez Hernández  
**Fecha base:** 2026-10-27  
**Producto:** Intelligent IT Operations & AI Automation Platform

## 1. Problema empresarial

Los equipos de soporte reciben solicitudes de conectividad, software, hardware y acceso que deben validarse, clasificar, relacionarse con procedimientos autorizados, resolverse o escalarse y, en ciertos casos, someterse a aprobación. Cuando el flujo depende de pasos manuales no uniformes, se pierde trazabilidad y resulta difícil explicar por qué se recomendó o ejecutó una acción.

OpsBridge AI será una plataforma local de demostración que organiza ese ciclo. Combina reglas empresariales deterministas con funciones de IA local opcionales. La IA apoya la clasificación y la redacción fundamentada; nunca sustituye las políticas, la autorización ni la validación de herramientas.

## 2. Objetivos y no objetivos

### 2.1 Objetivos

1. Registrar tickets válidos con identidad y trazabilidad.
2. Clasificar categoría y prioridad con reglas, o con IA local cuando esté disponible y evaluada.
3. Recuperar fragmentos de documentación autorizada y citar sus fuentes.
4. Recomendar procedimientos con una indicación inequívoca de modo (`rules`, `ai` o `unavailable`).
5. Consultar y operar solamente APIs simuladas locales mediante herramientas permitidas.
6. Exigir aprobación humana para acciones sensibles y separación de funciones.
7. Mostrar estados, historial, aprobaciones y métricas operativas verificables.
8. Evaluar clasificación, recuperación, fundamentación, seguridad y degradación con conjuntos reproducibles.
9. Producir evidencia técnica útil para un portafolio sin exagerar resultados.

### 2.2 No objetivos

- No reemplazar una mesa de servicio empresarial ni declarar preparación para producción.
- No conectarse a VPN, directorios, equipos, credenciales o infraestructura reales.
- No ejecutar comandos privilegiados o arbitrarios.
- No diagnosticar automáticamente cualquier problema de TI.
- No entrenar un modelo fundacional.
- No depender de una nube, API pagada, base vectorial administrada o servicio comercial.
- No usar datos personales reales ni documentación empresarial confidencial.

## 3. Usuarios y roles

| Rol | Necesidad | Facultades principales | Límites |
|---|---|---|---|
| Solicitante | Reportar y seguir su problema | Crear tickets; ver y comentar sus tickets; confirmar resolución | No reclasifica, aprueba ni ejecuta acciones |
| Técnico | Diagnosticar y gestionar trabajo | Ver cola; asignarse; clasificar; generar recomendación; proponer acciones; cambiar estados permitidos | No aprueba su propia propuesta; no ejecuta sin política válida |
| Aprobador | Controlar operaciones sensibles | Revisar evidencia; aprobar o rechazar una solicitud de acción | No altera parámetros al aprobar; una modificación crea nueva solicitud |

Para la demostración local se usarán cuentas sintéticas. La autorización se verifica en el servidor, nunca solo en la interfaz.

## 4. Alcance funcional

### 4.1 Capacidades

| ID | Requisito funcional |
|---|---|
| RF-01 | Crear un ticket con título, descripción, impacto, datos de contexto permitidos y consentimiento de uso local. |
| RF-02 | Emitir UUID interno y código legible único, guardar fecha UTC y autor. |
| RF-03 | Aplicar clasificación determinista y permitir clasificación IA opcional con versión, salida estructurada y procedencia. |
| RF-04 | Mantener categoría, prioridad, confianza declarada por el proveedor, justificación y revisión humana por separado. |
| RF-05 | Buscar únicamente documentos activos y autorizados, conservando documento, versión, sección y fragmento citado. |
| RF-06 | Generar una recomendación con pasos, límites, advertencias, fuentes y modo de generación. |
| RF-07 | Abstenerse cuando la evidencia no sea suficiente y proponer escalamiento o recopilación de datos. |
| RF-08 | Consultar el estado de servicios mediante un adaptador simulado de solo lectura. |
| RF-09 | Crear solicitudes de aprobación inmutables para acciones sensibles con parámetros normalizados y resumen de riesgo. |
| RF-10 | Aprobar o rechazar con identidad, comentario, sello temporal y comprobación de separación de funciones. |
| RF-11 | Ejecutar una acción aprobada una sola vez contra un simulador local y registrar entrada saneada, resultado y correlación. |
| RF-12 | Mantener una máquina de estados de ticket y rechazar transiciones inválidas. |
| RF-13 | Exponer una línea temporal append-only de eventos relevantes. |
| RF-14 | Mostrar dashboard, lista/detalle, análisis, historial, aprobaciones, métricas y configuración de IA local. |
| RF-15 | Detectar disponibilidad del proveedor local; degradar a reglas o marcar función no disponible sin afirmar uso de IA. |
| RF-16 | Ingerir una colección controlada de documentos sintéticos, con revisión y estado de autorización. |
| RF-17 | Proporcionar filtros, orden estable y paginación en colecciones. |
| RF-18 | Permitir exportar evidencia sintética de un ticket en JSON para demostración, sin secretos ni hashes de contraseña. |

### 4.2 Estados y transiciones

Estados: `new`, `triaged`, `in_progress`, `waiting_approval`, `waiting_requester`, `resolved`, `closed`, `cancelled`.

| Desde | Hacia | Actor/condición |
|---|---|---|
| `new` | `triaged` | Técnico o clasificación automática válida |
| `triaged` | `in_progress` | Técnico asignado |
| `in_progress` | `waiting_approval` | Existe propuesta sensible pendiente |
| `waiting_approval` | `in_progress` | Aprobación resuelta o expirada; la ejecución es un evento separado |
| `in_progress` | `waiting_requester` | Técnico solicita información/confirmación |
| `waiting_requester` | `in_progress` | Respuesta del solicitante |
| `in_progress` | `resolved` | Técnico registra resolución y evidencia |
| `resolved` | `closed` | Solicitante confirma o técnico cierra según política de demo |
| Cualquier estado no terminal | `cancelled` | Solicitante antes del trabajo o técnico con razón documentada |
| `resolved` | `in_progress` | Reapertura justificada |

`closed` y `cancelled` son terminales en la primera versión. La prioridad no autoriza por sí misma una transición.

## 5. Escenarios empresariales

### 5.1 Escenario principal: problema de conexión VPN

1. Una persona solicitante registra: “La VPN no conecta desde la red doméstica”, sistema operativo sintético, mensaje de error sin credenciales e impacto.
2. El backend valida longitud, formato, campos permitidos y sesión; crea `OPS-2026-000001` más UUID.
3. El clasificador por reglas identifica `network.vpn`; calcula prioridad a partir de impacto y urgencia. Si se habilita IA, su propuesta se almacena en paralelo y no ignora la matriz de prioridad.
4. El recuperador consulta documentos autorizados como “Guía VPN — diagnóstico básico”, conserva fragmentos y versiones.
5. El recomendador presenta pasos no destructivos: comprobar conectividad, hora del sistema, cliente, estado del servicio y código de error, con citas.
6. El técnico puede ejecutar `service_status.get` contra el simulador. La herramienta solo acepta un `service_code` enumerado.
7. Si se propone `vpn_session.reset` para una identidad sintética, el sistema normaliza parámetros y crea una aprobación; no ejecuta todavía.
8. Un aprobador distinto revisa alcance y evidencia. Una aprobación está ligada al hash de acción y expira.
9. El ejecutor verifica rol, estado, vigencia, hash, idempotencia y allowlist; ejecuta una sola vez en el simulador.
10. La línea temporal registra solicitud, clasificación, fuentes, recomendación, consulta, aprobación, ejecución y resultado. El técnico resuelve y el solicitante confirma.

### 5.2 Problema de software

Una aplicación sintética no inicia. Reglas la clasifican como `software.application`; RAG recupera la guía versionada. El flujo recomienda recopilar versión y error, revisar estado simulado y reparar configuración solo en el simulador. La reinstalación simulada requiere aprobación; nunca se ejecutan instaladores reales.

### 5.3 Equipo de cómputo

Un equipo sintético muestra poco espacio y lentitud. La categoría canónica es `hardware.endpoint`. Se consultan pautas seguras de diagnóstico. La recomendación evita borrar archivos; una acción simulada de limpieza de caché requiere aprobación. Si hay señales de fallo físico, el sistema se abstiene y escala.

### 5.4 Solicitud de acceso

Una persona solicita acceso a una aplicación sintética. La categoría es `access.application`. El sistema exige recurso y justificación, recupera la política de mínimo privilegio y crea una propuesta con rol enumerado. Toda concesión simulada requiere aprobador distinto y nunca maneja contraseñas ni modifica directorios reales.

## 6. Reglas empresariales esenciales

- Prioridad se deriva de una matriz versionada `impact × urgency`; la IA no puede aumentarla o reducirla fuera de esa política, aunque puede sugerir contexto para revisión.
- Documentos y fragmentos recuperados son datos no confiables; no contienen autoridad para invocar herramientas o alterar políticas.
- Solo el catálogo del servidor define herramientas, parámetros y sensibilidad.
- Toda operación mutante exige `Idempotency-Key`; el mismo cuerpo devuelve el resultado previo y un cuerpo diferente produce conflicto.
- Una aprobación referencia `action_type`, parámetros canónicos, ticket, proponente, política y hash; no se puede reutilizar.
- Un solicitante o proponente no puede aprobar su propia acción.
- Las aprobaciones expiran y son de un solo uso. Fallos ambiguos no se reintentan automáticamente para acciones mutantes.
- No se ejecuta una propuesta generada por IA de forma directa.

## 7. Requisitos no funcionales

| ID | Requisito y verificación prevista |
|---|---|
| RNF-01 Seguridad | Denegación por defecto, RBAC en servidor, sesiones seguras, CSRF, validación estricta y pruebas negativas. |
| RNF-02 Auditabilidad | Todo cambio relevante produce evento correlacionado; auditoría no expone secretos ni texto completo innecesario. |
| RNF-03 Confiabilidad | Transacciones atómicas; timeouts; errores tipados; idempotencia; simulación de fallos y reintentos seguros. |
| RNF-04 Rendimiento local | Presupuestos iniciales, no resultados: API CRUD p95 objetivo ≤300 ms y búsquedas FTS p95 ≤500 ms con dataset de demo en equipo de referencia; medir antes de afirmar. LLM queda fuera de ese presupuesto y muestra progreso/cancelación. |
| RNF-05 Accesibilidad | Navegación por teclado, foco visible, etiquetas, errores asociados, contraste WCAG 2.2 AA y pruebas automatizadas más revisión manual. |
| RNF-06 Responsive | Flujos críticos utilizables a 360 px, 768 px y escritorio; tablas pasan a tarjetas o desplazamiento etiquetado. |
| RNF-07 Portabilidad | Windows como entorno inicial; comandos documentados; rutas sin supuestos globales; posterior validación Linux. |
| RNF-08 Reproducibilidad | Lockfiles, migraciones, semillas sintéticas, `.env.example` y prueba de instalación limpia. |
| RNF-09 Mantenibilidad | Capas y dependencias unidireccionales; tipado; lint; pruebas por frontera; ADR para cambios mayores. |
| RNF-10 Privacidad | Minimización, datos sintéticos, redacción en logs y borrado administrativo fuera de auditoría según política de demo. |
| RNF-11 Observabilidad | Logs JSON con `correlation_id`, métricas locales no sensibles y health/readiness separados. |
| RNF-12 Disponibilidad IA | Cada resultado declara proveedor, modelo, versión/configuración, modo y error de degradación; nunca simula éxito de IA. |

Los presupuestos son criterios de diseño pendientes de medición, no métricas alcanzadas.

## 8. Experiencia de usuario

### 8.1 Navegación y vistas

- **Dashboard:** totales por estado/prioridad, pendientes de aprobación, antigüedad y estado de integraciones. No usar métricas ficticias; las semillas se etiquetan como demo.
- **Nuevo ticket:** formulario por pasos breves, validación inline y resumen antes de enviar.
- **Solicitudes:** filtros persistentes en URL, búsqueda, orden, paginación y estados vacíos útiles.
- **Detalle:** encabezado operativo, contexto, recomendación/citas, acciones permitidas y línea temporal.
- **Análisis:** compara reglas e IA, muestra modo, advertencias, fuentes y revisión humana.
- **Aprobaciones:** alcance, parámetros, riesgo, proponente, vencimiento y decisión explícita.
- **Métricas:** definiciones visibles, periodo y ausencia de datos diferenciada de cero.
- **Configuración IA:** disponibilidad, modelo local configurado, prueba de conexión y degradación; no descarga modelos sin acción explícita.

### 8.2 Lineamientos visuales

Diseño sobrio de consola operativa: jerarquía tipográfica clara, ancho legible, escala de espaciado consistente y color semántico acompañado de texto/icono. Los estados de carga usan esqueletos o indicadores con etiqueta; los errores explican qué ocurrió, qué se conservó y cómo reintentar. Confirmaciones describen el efecto real. Evitar animaciones decorativas, indicadores ambiguos y dashboards saturados.

## 9. Criterios de aceptación de producto

| ID | Criterio observable |
|---|---|
| CA-01 | Un solicitante crea un ticket válido y recibe UUID/código único; entradas inválidas no persisten. |
| CA-02 | La máquina de estados acepta transiciones documentadas y devuelve conflicto para las demás. |
| CA-03 | Reglas clasifican los cuatro escenarios base de forma reproducible y registran versión de reglas. |
| CA-04 | Con IA deshabilitada, la UI/API indican `rules` o `unavailable`, nunca `ai`. |
| CA-05 | Toda recomendación IA válida cita fragmentos autorizados; sin evidencia suficiente se abstiene. |
| CA-06 | Documentos con instrucciones maliciosas no cambian políticas ni invocan herramientas. |
| CA-07 | Un técnico propone una acción sensible, pero no puede ejecutarla antes de una aprobación válida. |
| CA-08 | El proponente no puede autoaprobar; una aprobación alterada, vencida o reutilizada es rechazada. |
| CA-09 | Dos solicitudes mutantes iguales con la misma clave no producen efectos duplicados. |
| CA-10 | Cada paso del flujo VPN aparece en una línea temporal con actor, tiempo, correlación y resultado saneado. |
| CA-11 | Fallos de Ollama y simuladores devuelven estados controlados y permiten continuar con trabajo no dependiente. |
| CA-12 | Los tres roles solo ven y ejecutan operaciones autorizadas, comprobado por matriz de pruebas. |
| CA-13 | Los flujos críticos pasan E2E en viewport móvil y escritorio y una auditoría de accesibilidad definida. |
| CA-14 | Una instalación limpia puede migrar, sembrar, iniciar backend/frontend y ejecutar pruebas con documentación vigente. |

## 10. Matriz de competencias de portafolio

| Módulo/evidencia futura | Competencias demostrables con código y pruebas | Roles relacionados | Estado |
|---|---|---|---|
| Dominio y máquina de estados | Modelado, invariantes, arquitectura limpia, pruebas unitarias | Software, Backend | Pendiente Fase 2 |
| REST/OpenAPI/persistencia | FastAPI, Pydantic, SQLAlchemy, migraciones, contratos, idempotencia | Backend, Software | Pendiente Fase 2 |
| SPA accesible | React/TypeScript, UX operativa, manejo de estado y errores | Software | Pendiente Fase 3 |
| Clasificación dual | Baseline por reglas, salida estructurada, comparación y degradación | AI, Applied AI | Pendiente Fase 4 |
| RAG con evidencia | Ingesta, recuperación, citas, abstención y evaluación | Applied AI, AI Integration | Pendiente Fase 4 |
| Automatización aprobada | Tool gateway, policy enforcement, HITL, idempotencia | AI Automation, IT Automation | Pendiente Fases 2 y 4 |
| QA y seguridad | pytest, integración, Playwright, amenazas, casos adversariales | QA Automation, Software | Diseño actual; evidencia Fases 2–5 |
| Observabilidad/evaluación | Auditoría, métricas reproducibles, datasets etiquetados | AI, QA, Backend | Pendiente Fases 4–5 |

La Fase 1 demuestra análisis y diseño documentado; todavía no demuestra implementación ni resultados. La investigación externa de vacantes permanece fuera del alcance de esta fase.

## 11. Dependencias y supuestos por validar

- El hardware disponible para modelos locales no se ha inventariado; modelo, cuantización y latencia quedan pendientes de un benchmark en Fase 4.
- El entorno inicial es Windows; PostgreSQL y contenedores son rutas de evolución, no requisitos locales actuales.
- La taxonomía y documentos de demo serán sintéticos y versionados.
- Los objetivos de rendimiento y calidad requieren medición con dataset y equipo de referencia documentados.
