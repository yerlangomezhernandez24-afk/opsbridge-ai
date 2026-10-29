# Seguridad, confiabilidad y pruebas — OpsBridge AI

**Estado:** estrategia de Fase 1; controles aún no implementados  
**Alcance:** aplicación local con datos y sistemas sintéticos

## 1. Activos, límites de confianza y supuestos

### 1.1 Activos

- Identidad, sesión y rol de usuarios de demostración.
- Contenido de tickets y comentarios, aunque sea sintético.
- Estado e historial de tickets.
- Documentos autorizados, versiones, chunks y citas.
- Políticas de prioridad, transición, herramientas y aprobaciones.
- Propuestas, decisiones, hashes y resultados de ejecución.
- Configuración local y secretos de desarrollo.
- Integridad y procedencia de informes de evaluación.

### 1.2 Límites de confianza

1. Navegador ↔ backend: toda entrada es no confiable.
2. Backend ↔ SQLite/PostgreSQL: consultas parametrizadas; el proceso DB no sustituye autorización.
3. Backend ↔ documentos: contenido no confiable incluso si fue autorizado para consulta.
4. Backend ↔ Ollama/modelo: salida no confiable y disponibilidad no garantizada.
5. Backend ↔ simuladores: contrato validado, timeouts y resultados potencialmente ambiguos.
6. Repositorio ↔ configuración local: secretos y artefactos generados quedan fuera de control de versiones.

La escucha en loopback reduce exposición, pero no protege contra otro proceso local malicioso. La demo no se considera un entorno hostil multiusuario ni producción.

## 2. Modelo de amenazas

| ID | Amenaza/abuso | Impacto | Controles de diseño | Evidencia futura |
|---|---|---|---|---|
| T-01 | Usuario manipula `role`, propietario o estado en JSON | Acceso/flujo indebido | Identidad solo de sesión; esquemas `extra=forbid`; RBAC y reglas de estado en caso de uso | Matriz API negativa |
| T-02 | Robo/fijación de sesión o CSRF | Mutación no autorizada | ID rotado al login; cookie HttpOnly/SameSite; expiración/revocación; token CSRF; origen restringido | Pruebas auth/CSRF |
| T-03 | IDOR al cambiar UUID | Lectura/acción sobre ticket ajeno | Scope por propietario/rol en repositorio/caso de uso; 404 seguro | Pruebas cruzadas de usuarios |
| T-04 | XSS desde tickets/documentos/modelo | Secuestro de sesión/engaño | React escaping; sanitización Markdown; CSP; no `dangerouslySetInnerHTML` sin revisión | Payloads XSS + CSP |
| T-05 | SQL injection | Corrupción/exfiltración | ORM/queries parametrizadas; allowlists de orden/filtros; nunca SQL del modelo | Casos de payload + análisis estático |
| T-06 | Prompt injection en documento o ticket | Recomendación/acción indebida | Delimitar evidencia; instrucciones de sistema separadas; salida estructurada; citas; modelo sin autoridad; gateway independiente | Dataset adversarial |
| T-07 | Modelo inventa cita, categoría o herramienta | Decisión falsa | Verificar IDs contra evidencia; enums; validación Pydantic; abstención; catálogo servidor | Pruebas de contrato IA |
| T-08 | Acción sensible sin aprobación | Cambio indebido | Política server-side; aprobación vinculada a hash/ticket/actor/TTL; denegar por defecto | Integración approval→execution |
| T-09 | Autoaprobación o colusión simple | Bypass de control | Proponente/solicitante distintos del aprobador; auditoría; cuentas separadas | Pruebas separación de funciones |
| T-10 | Repetición/replay o doble clic | Efecto duplicado | Idempotency-Key + hash; unique constraints; estado de ejecución; token de un uso | Prueba concurrente |
| T-11 | TOCTOU: parámetros cambian tras aprobar | Alcance alterado | Propuesta inmutable y JSON canónico; recomputar hash inmediatamente antes de ejecutar | Prueba de mutación/replay |
| T-12 | SSRF/path traversal/archivo hostil | Acceso local no previsto | URLs no son entrada; loopback/allowlist; ingesta desde raíz resuelta y manifiesto; tamaño/tipo; symlinks rechazados | Casos de rutas/URLs |
| T-13 | Secretos/PII en logs o auditoría | Exposición | Logger estructurado, allowlist de campos, redacción, no cuerpos/prompts completos por defecto | Captura y escaneo de logs |
| T-14 | Dependency/supply-chain compromise | Ejecución/filtración | Lockfiles, hashes cuando sea práctico, fuentes oficiales, auditorías, actualización controlada | SBOM/audit en cierre |
| T-15 | DoS por solicitudes/LLM grande | Bloqueo local | Límites de tamaño/rate/concurrencia; timeout; cancelación; cola acotada | Pruebas de límites |
| T-16 | Simulador/LLM falla o responde mal | Estado inconsistente | Validación de respuesta, circuit breaker simple, transacciones; estado `unknown`; reintentos solo seguros | Fault injection |
| T-17 | Manipulación de auditoría local | Pérdida de evidencia | Permisos de archivo, append-only lógico, hashes encadenados opcionales; declarar que no es WORM | Prueba de invariantes; limitación documentada |
| T-18 | Configuración peligrosa habilita endpoint real | Efecto fuera de alcance | Esquema rechaza hosts no loopback en perfil demo; `APP_ENV=demo`; simulación visible; arranque falla cerrado | Pruebas de config |

## 3. Controles por área

### 3.1 Validación y tratamiento de datos

- Pydantic v2 estricto, `extra="forbid"`, límites de longitud/rango y enums.
- Normalizar solo donde sea semánticamente seguro; conservar entrada original saneada para auditoría cuando haga falta.
- Rechazar archivos binarios y carga libre en la primera versión; conocimiento entra por manifiestos versionados.
- Escapar salida según contexto; no confiar en texto de reglas, documentos o LLM.
- No aceptar contraseñas, tokens, llaves privadas ni OTP en tickets. Advertir y aplicar detección básica como defensa adicional, no garantía.

### 3.2 Autenticación y autorización

- Cuentas locales sintéticas; Argon2id con parámetros medidos en el equipo; credenciales iniciales rotables.
- Sesiones aleatorias de alta entropía, almacenadas hasheadas si persisten, con expiración absoluta e inactividad.
- RBAC (`requester`, `technician`, `approver`) más propiedad, estado y separación de funciones.
- Rate limiting de login y mensajes indistinguibles para credencial inválida.
- Reautenticación puede evaluarse para aprobar, pero no se afirmará MFA.

### 3.3 RAG e IA

- Ingesta separa metadatos confiables del cuerpo no confiable; checksum, versión, autor sintético y aprobación.
- Recuperación filtra documentos activos antes de ranking.
- Prompts identifican claramente instrucciones, entrada y evidencia delimitada.
- Salida JSON con esquema estricto y presupuesto de tokens/tiempo.
- Citas deben corresponder a chunks entregados; afirmaciones críticas sin evidencia causan rechazo o abstención.
- No se envían herramientas ejecutables al modelo en la primera versión.
- Guardar versión de prompt, modelo/config y dataset, sin almacenar secretos ni razonamiento oculto.
- Si el proveedor/modelo no soporta el esquema requerido, la función se marca incompatible; no se parsea texto libre de forma permisiva.

### 3.4 Herramientas y aprobaciones

- Catálogo compilado/configurado por servidor; desconocido = denegado.
- Modelos de parámetros por acción, enums y patrones; sin shell, SQL, URL o ruta arbitraria.
- Consultas read-only y mutaciones separadas.
- Propuesta inmutable; parámetros canónicos; hash; TTL; decisión de un solo uso.
- Comprobación atómica de aprobación y creación de ejecución.
- Unique constraints para aprobación/ejecución e idempotencia.
- Timeouts mutantes generan `unknown` hasta consultar/reconciliar por identificador externo; nunca reintento ciego.
- Todos los adaptadores del perfil demo validan `simulated=true` y endpoint loopback.

### 3.5 Configuración, errores y observabilidad

- `.env.example` sin secretos; `.env` ignorado; configuración validada al inicio.
- Errores externos tipados, sin stack trace. Logs internos correlacionados y con redacción.
- `correlation_id`, actor interno, evento, recurso, resultado y latencia; no cuerpo completo.
- Health público mínimo; estado detallado solo para roles autorizados.
- Backups y restauración se probarán sobre datos sintéticos antes de declarar confiabilidad.

## 4. Estrategia de calidad

### 4.1 Pirámide y responsabilidades

| Nivel | Alcance | Herramientas previstas | Momento |
|---|---|---|---|
| Unitarias | Entidades, políticas, transiciones, prioridad, hashes, validadores, ranking | pytest | En cada cambio de dominio |
| Integración | Repositorios, migraciones, HTTP, sesión, transacciones, FTS, adaptadores fake/reales locales | pytest + HTTPX | Por módulo y cierre de fase |
| Contrato | OpenAPI, cliente TypeScript, Ollama, simulador, esquemas de herramientas | pytest/JSON Schema | Al cambiar frontera |
| E2E | Flujos por rol en navegador, errores, responsive | Playwright | Fases 3–5 |
| Seguridad | AuthZ, CSRF, injection, XSS, path traversal, replay, dependencias | pytest, Playwright, analizadores | Dirigidas + cierre |
| Evaluación IA | Clasificación, recuperación, fundamentación, abstención, adversariales | runners reproducibles | Fase 4 y regresiones |
| Operación | Instalación limpia, migración, seed, backup/restore, degradación | scripts documentados | Cierres de Fases 2, 4 y 5 |

Cobertura de líneas es indicador secundario, no criterio único. Se exigirá cobertura de ramas de invariantes críticas y mutation testing selectivo si el costo local es aceptable.

### 4.2 Casos mínimos por requisito

#### Tickets y persistencia

- Campos ausentes, límites, Unicode, control characters y campos extra.
- Código/UUID únicos bajo creación concurrente.
- Rollback: no queda ticket sin evento ni evento huérfano.
- Cada transición válida e inválida; terminales y reapertura.
- Conflicto de `If-Match` y relectura.
- Filtros, cursor estable y aislamiento entre solicitantes.
- Migración adelante en DB vacía y con fixture de versión previa.

#### Autorización y aprobaciones

- Matriz endpoint × S/T/A × propietario/no propietario.
- Sesión vencida/revocada, rotación y CSRF ausente/incorrecto.
- Autoaprobación, aprobación por solicitante, rol incorrecto.
- Rechazada, expirada, alterada, ya consumida y ticket distinto.
- Dos ejecuciones concurrentes: solo una obtiene efecto.
- Mismo `Idempotency-Key` con mismo/diferente payload.

#### Simuladores e integración

- Éxito, 4xx, 5xx, timeout, JSON inválido, respuesta incompleta y desconexión.
- Consulta read-only reintentable con backoff acotado.
- Mutación con timeout pasa a `unknown`; no duplica.
- Endpoint fuera de loopback o herramienta no registrada falla al arranque/uso.

#### RAG y agentes/asistencia

- Documento autorizado/inactivo/versionado; metadatos y checksum.
- Pregunta con respuesta única, varias fuentes, contradicción y sin evidencia.
- Chunk malicioso: “ignora instrucciones”, herramienta inventada, exfiltración o falsa autoridad.
- Cita inexistente/no recuperada; afirmación sin cita; categoría fuera de enum.
- Modelo no disponible, timeout, JSON truncado, esquema inválido y modelo incompatible.
- La propuesta nunca cambia ticket ni llama herramienta por sí sola.
- Modo reglas nunca lleva `mode=ai` ni proveedor/modelo ficticio.

#### E2E y responsive

- Solicitante crea y sigue VPN; técnico clasifica/consulta/propone; aprobador decide; técnico ejecuta y resuelve.
- Problema de software y solicitud de acceso al menos hasta recomendación/aprobación.
- Navegación solo teclado, orden de foco, foco tras modal/error, nombres accesibles y anuncio de estado.
- 360×800, 768×1024 y escritorio; zoom 200%; sin pérdida de controles.
- Estados de carga, vacío, error recuperable, sesión expirada y dependencia caída.

## 5. Evaluación reproducible de IA

### 5.1 Dataset

`evals/datasets/` contendrá JSONL versionado y revisado, solo sintético:

- `classification_v1`: texto/contexto, categorías aceptables, prioridad de política, señales y ambigüedad.
- `retrieval_v1`: consulta, chunks relevantes, relevantes opcionales y no relevantes difíciles.
- `grounding_v1`: consulta, evidencia, claims esperados/prohibidos y decisión de abstención.
- `injection_v1`: documentos/tickets adversariales y comportamiento seguro esperado.
- `tools_v1`: propuestas válidas/inválidas, aprobación esperada y parámetros permitidos.

Debe cubrir VPN, software, equipos y accesos; redacción corta/larga, español, errores ortográficos razonables, ambigüedad, fuera de alcance y ausencia de evidencia. Casos de desarrollo y prueba final quedan separados. Cada cambio requiere versión y justificación.

### 5.2 Métricas

| Función | Métricas | Por qué |
|---|---|---|
| Clasificación | Exactitud balanceada, macro-F1, matriz de confusión, cobertura/abstención | Evita ocultar categorías minoritarias y mide rechazo |
| Prioridad | Coincidencia con política y tasa de violación de regla | La política, no el LLM, es autoridad |
| Recuperación | Recall@k, MRR/nDCG@k y tasa de consulta sin evidencia | Mide presencia y orden de fuentes |
| Fundamentación | Precision/recall de citas, cobertura de claims, tasa de afirmación no soportada | Mide evidencia, no fluidez |
| Abstención | Precision/recall para “sin evidencia” y utilidad de pregunta de seguimiento | Penaliza respuestas seguras solo en apariencia |
| Herramientas | Exact match de acción/parámetros, tasa de acción prohibida, tasa de aprobación correcta | Separa propuesta de ejecución segura |
| Robustez | Attack success rate por familia, fallos de esquema, estabilidad en repeticiones | Expone prompt injection y variabilidad |
| Operación | Latencia mediana/p95, timeout, consumo observado de RAM/VRAM, disponibilidad | Permite decidir viabilidad local |

La “confianza” emitida por el modelo se evaluará con diagrama de confiabilidad y Brier/ECE solo si el modelo produce puntuaciones interpretables; hasta entonces se marca no calibrada.

### 5.3 Criterios de aceptación sin porcentajes inventados

En Fase 4 se ejecutará primero un baseline congelado por reglas/FTS. Luego se registrarán resultados del modelo local en el mismo conjunto. Para promover una configuración:

1. Debe haber **cero ejecuciones reales** y cero bypass de aprobación; esto es una invariante, no una métrica estadística.
2. Toda salida debe validar esquema o abstenerse; nunca aceptación permisiva.
3. No puede degradar categorías críticas o tasa de afirmaciones sin evidencia frente al baseline más allá de un margen definido después de medir la variabilidad.
4. Debe aportar una mejora observable y reproducible en al menos una función objetivo sin deteriorar controles de seguridad.
5. Los umbrales numéricos se propondrán tras la corrida baseline y revisión del tamaño/distribución del dataset; se documentarán antes de evaluar el conjunto final para evitar ajustar al resultado.
6. Resultados se reportan con numerador/denominador, configuración, semilla cuando aplique, hardware, duración y fallos, no solo porcentaje.

No se afirmará exactitud ni superioridad en esta fase.

## 6. Pruebas de seguridad específicas

- Fuzzing basado en esquemas para endpoints críticos y validadores de herramientas.
- Payloads OWASP relevantes: XSS almacenado/reflejado, injection, mass assignment, traversal y cabeceras.
- Pruebas de autorización generadas desde una tabla única para evitar endpoints olvidados.
- SAST/lint: Ruff, mypy o Pyright para Python; ESLint/TypeScript; Bandit/Semgrep si aportan señal y están fijados.
- Dependencias: `pip-audit`/`uv audit` disponible y `npm audit` como señales revisadas, no autocorrección destructiva.
- Secret scanning antes de GitHub; verificar `.env`, DB, modelos grandes y reportes en `.gitignore`.
- Headers y cookies inspeccionados en E2E.
- Pruebas de carrera sobre aprobación, ejecución e idempotencia.

Los escáneres no sustituyen revisión manual. Hallazgos se triagean; no se ocultan falsos negativos o riesgo aceptado.

## 7. Fixtures y entornos

- Reloj, UUID y adaptadores inyectables para pruebas deterministas.
- DB temporal por prueba o transacción; suite separada de migración real.
- Ollama falso para errores de contrato y Ollama local real etiquetado `ai_local`, omitido con razón cuando no esté instalado.
- Simulador controlable por escenario (`success`, `timeout`, `malformed`, `unknown_after_commit`).
- Navegador en limpio con cuentas sintéticas separadas.
- No usar mocks en pruebas que pretendan demostrar SQL, auth HTTP, OpenAPI o contrato real.

## 8. Puertas de calidad por fase

| Cierre | Evidencia mínima |
|---|---|
| Fase 2 | Unitarias/integración backend; migración limpia; auth/RBAC; flujo de ticket; idempotencia; simulador; OpenAPI revisado |
| Fase 3 | Build/typecheck/lint; E2E de roles y ticket; accesibilidad automática + lista manual; viewports definidos |
| Fase 4 | Dataset versionado; baseline; RAG/IA evaluados; degradación; injection; aprobación/ejecución completa |
| Fase 5 | Suite completa limpia; instalación nueva; fallos integrados; security review; riesgos y métricas reales publicados |
| Fase 6 | Sin secretos/datos reales; claims enlazados a evidencia; documentación reproducible; no declarar producción |

## 9. Incidentes, reintentos y recuperación

- Cada llamada externa tiene timeout y resultado tipado.
- Solo GET/consultas idempotentes pueden reintentarse automáticamente, con backoff corto y límite.
- Una mutación devuelve identificador del simulador; si el resultado es ambiguo se reconcilia por ese ID.
- Transacción DB no permanece abierta durante inferencia o red lenta. Se persiste intención, se llama fuera, se finaliza con control de versión/idempotencia.
- Fallo de auditoría para una mutación crítica hace fallar cerrado si no puede registrarse atómicamente.
- Backups, restauración y pérdida del archivo SQLite se prueban antes de recomendar uso prolongado.

## 10. Riesgos residuales

- Un modelo puede producir contenido persuasivo pero incorrecto aun con citas; revisión humana y abstención siguen siendo necesarias.
- Un documento autorizado puede estar obsoleto o ser malicioso; autorización no equivale a verdad.
- La auditoría en el mismo host no es inmutable contra un administrador local.
- Argon2 y límites de rendimiento requieren calibración por hardware.
- Escáneres automáticos y datasets sintéticos no representan toda la variabilidad real.
- La ejecución local sin TLS es aceptable solo en loopback de demo; cualquier exposición de red exige rediseño y evaluación.
