# Diseño de API — OpsBridge AI

**Base URL:** `/api/v1`  
**Formato:** JSON UTF-8  
**Contrato:** OpenAPI generado por FastAPI y comprobado en CI futuro

## 1. Convenciones

- Nombres JSON en `snake_case`; tiempos RFC 3339 en UTC; identificadores UUID como cadenas.
- Código humano de ticket: `OPS-YYYY-NNNNNN`; no se usa como clave de seguridad.
- Colecciones: `page_size` (predeterminado 25, máximo 100) y cursor opaco `next_cursor`. Orden total estable por `created_at DESC, id DESC`.
- Filtros repetibles o separados por coma se documentarán por endpoint; valores desconocidos se rechazan.
- La creación de tickets exige `Idempotency-Key` UUID v4 con 24 h de retención. El alcance es usuario+operación+clave; misma huella reproduce la instantánea de respuesta confirmada y distinta carga devuelve `409`. La limpieza de expirados es oportunista al crear.
- Actualizaciones de agregados usan `ETag: "<version>"` e `If-Match`; versión obsoleta devuelve `412`.
- `X-Correlation-ID` válido puede venir del cliente; el servidor genera uno si falta y siempre lo retorna.
- La API nunca devuelve hashes de contraseña, cookies, secretos, prompts de sistema ni trazas internas.

## 2. Autenticación, CSRF y permisos

La demo usa una sesión opaca en cookie `opsbridge_session` (`HttpOnly`, `SameSite=Lax`; `Secure` cuando exista TLS). Solo el verificador SHA-256 del token aleatorio se persiste. `POST /api/v1/auth/login` exige el `Origin` local configurado, rota cualquier sesión presentada y responde `204` estableciendo la cookie; no devuelve el token en JSON. `POST /api/v1/auth/logout` exige el mismo `Origin`, sesión válida y `X-CSRF-Token`, luego revoca la sesión y responde `204`. `GET /api/v1/auth/session` devuelve identidad, rol, permisos, CSRF ligado a la sesión y expiración de inactividad, siempre con `Cache-Control: no-store`. En desarrollo, CORS solo permite el origen exacto configurado y credenciales.

La sesión expira a las 8 horas de forma absoluta y tras 30 minutos de inactividad por defecto; ambos valores son configurables dentro de límites validados. El login se limita por proceso a cinco fallos por identificador normalizado en cinco minutos, con bloqueo de cinco minutos y `Retry-After: 300`. Las credenciales inválidas y las cuentas inexistentes reciben la misma respuesta pública.

Abreviaturas: `S` solicitante, `T` técnico, `A` aprobador. La posesión se comprueba además del rol.

## 3. Recursos y endpoints

### 3.1 Sistema y sesión

| Método/ruta | Permiso | Propósito |
|---|---|---|
| `GET /health/live` | Público local | Liveness sin consultar dependencias |
| `GET /health/ready` | Público local, respuesta mínima | Estado de DB/migraciones sin detalles sensibles |
| `POST /api/v1/auth/login` | Anónimo | Crear sesión con cuenta sintética |
| `POST /api/v1/auth/logout` | S/T/A | Revocar sesión actual |
| `GET /api/v1/auth/session` | S/T/A | Usuario, roles, permisos, CSRF y expiración |
| `GET /api/v1/integrations/status` | T/A | Ollama, recuperación y simulador; no revela rutas/secretos |

### 3.2 Tickets

| Método/ruta | Permiso | Propósito |
|---|---|---|
| `POST /tickets` | S/T | Crear ticket; idempotencia requerida |
| `GET /tickets` | S propios; T/A todos | Listar con `status`, `priority`, `category`, `assignee_id`, `query`, cursor |
| `GET /tickets/{ticket_id}` | S propietario; T/A | Detalle y enlaces permitidos |
| `PATCH /tickets/{ticket_id}` | T autorizado | Editar categoría/impacto/urgencia con `If-Match`; no cambia estado |
| `POST /tickets/{ticket_id}/transitions` | S propietario/T autorizado | Solicitar transición tipada con `If-Match` |
| `GET /tickets/{ticket_id}/transition-options` | S propietario/T autorizado | Opciones autorizadas y campos requeridos calculados por servidor |
| `POST /tickets/{ticket_id}/assignment` | T | Asignar/desasignar con versión |
| `POST /tickets/{ticket_id}/comments` | S propietario/T/A | Comentario visible según `visibility` permitido |
| `GET /tickets/{ticket_id}/timeline` | S propietario/T/A | Eventos presentables, paginados |
| `GET /tickets/{ticket_id}/export` | T/A | Evidencia JSON saneada, solo datos sintéticos |

La API no acepta afirmaciones del cliente como `approval_resolved` o `approval_reference`. En este corte, entrar en `waiting_approval` o reanudar desde ese estado está bloqueado en la capa de aplicación: se habilitará únicamente cuando exista evidencia de aprobación persistida y validada por servidor. El flujo VPN usa su contrato independiente de propuestas, decisión por otro actor, versión y ejecución única.

### 3.3 Análisis, conocimiento y recomendaciones

| Método/ruta | Permiso | Propósito |
|---|---|---|
| `POST /tickets/{id}/classifications` | T o automatización interna | Ejecutar `rules` o `ai`; IA puede estar deshabilitada |
| `GET /tickets/{id}/classifications` | S propietario/T/A | Historial y revisión humana |
| `POST /tickets/{id}/retrievals` | T | Recuperar evidencia autorizada para una pregunta acotada |
| `GET /tickets/{id}/retrievals/{run_id}` | S propietario/T/A | Chunks/citas y configuración no sensible |
| `POST /tickets/{id}/recommendations` | T | Generar por plantilla/reglas o IA local |
| `GET /tickets/{id}/recommendations` | S propietario/T/A | Historial, fuentes, modo y estado de validación |
| `POST /recommendations/{id}/reviews` | T | Aceptar, editar como nueva revisión o rechazar |
| `GET /knowledge/documents` | T/A | Documentos y versiones autorizadas |
| `POST /knowledge/documents/ingestions` | A | Ingesta desde ubicación local permitida; no carga arbitraria en v1 |

### 3.4 Herramientas, aprobaciones y ejecuciones

| Método/ruta | Permiso | Propósito |
|---|---|---|
| `GET /tool-catalog` | T/A | Catálogo público interno, sensibilidad y esquemas permitidos |
| `POST /tickets/{id}/tool-queries` | T | Ejecutar consulta de solo lectura permitida |
| `POST /tickets/{id}/action-proposals` | T | Crear propuesta inmutable; nunca ejecuta |
| `GET /approval-requests` | A; T propias en lectura | Cola filtrable por estado/ticket |
| `GET /approval-requests/{id}` | A; proponente | Detalle y hash canónico |
| `POST /approval-requests/{id}/decisions` | A distinto del proponente/solicitante | Aprobar/rechazar; idempotencia y `If-Match` |
| `POST /approval-requests/{id}/executions` | T autorizado o caso de uso interno | Ejecutar una vez si la aprobación sigue válida |
| `GET /tickets/{id}/executions` | S propietario con vista reducida; T/A | Resultados saneados |

### 3.5 Dashboard y métricas

| Método/ruta | Permiso | Propósito |
|---|---|---|
| `GET /dashboard/summary?from=&to=` | T/A | Conteos y antigüedad, con definiciones |
| `GET /tickets/summary?status=&priority=&category=&assignee_id=&query=` | S/T/A | Agregados del alcance completo autorizado; S queda limitado a tickets propios |
| `GET /metrics/operations?from=&to=&group_by=` | T/A | Series agregadas sin datos personales |
| `GET /metrics/ai-evaluations` | T/A | Solo informes realmente ejecutados y versión de dataset |

## 4. Esquemas principales

### 4.1 Crear ticket

```json
{
  "title": "No puedo conectar a la VPN de demostración",
  "description": "El cliente muestra el código DEMO-104 desde mi red doméstica.",
  "category": "network.vpn",
  "impact": "single_user",
  "urgency": "medium"
}
```

Reglas implementadas en 2.3B: título 5–160 caracteres; descripción 20–4000; categoría, impacto y urgencia enumerados. `requester_id`, rol, estado y versión no se aceptan del cliente. El contexto estructurado se pospone hasta existir soporte de dominio/persistencia; no se acepta para evitar descartarlo silenciosamente.

Respuesta `201`:

```json
{
  "data": {
    "id": "4af05bb6-0f02-4d3e-bc20-6617afad57cf",
    "key": "OPS-2026-000001",
    "status": "new",
    "priority": "p3",
    "priority_source": "policy:impact-urgency-v1",
    "created_at": "2026-10-27T18:30:00Z",
    "version": 1
  },
  "meta": {"correlation_id": "35d27626-fc58-4557-b67a-f8ec514b4ced"}
}
```

### 4.2 Clasificación

Solicitud:

```json
{
  "mode": "ai",
  "taxonomy_version": "support-taxonomy-v1"
}
```

Respuesta `201` válida:

```json
{
  "data": {
    "id": "dd53c7fc-6543-4e35-8f24-b6289a3079e0",
    "mode": "ai",
    "provider": "ollama",
    "model": "configured-local-model",
    "category": "network.vpn",
    "suggested_priority": "p3",
    "policy_priority": "p3",
    "confidence": {"value": 0.78, "calibrated": false},
    "signals": ["vpn", "connection_error"],
    "review_status": "pending",
    "created_at": "2026-10-27T18:31:00Z"
  }
}
```

Si IA no está disponible: `503 AI_PROVIDER_UNAVAILABLE`; el cuerpo incluye `fallback_available: true` cuando pueda solicitarse `mode: rules`. La API no devuelve un resultado por reglas etiquetado como IA.

### 4.3 Recuperación y recomendación

Solicitud:

```json
{
  "mode": "ai",
  "retrieval_run_id": "d6bb2c12-44db-4f23-87d6-8ad25bc7f16b",
  "intent": "troubleshooting"
}
```

Respuesta abreviada:

```json
{
  "data": {
    "id": "156fdd56-33cf-4a4b-8b47-ad9267b80ae2",
    "mode": "ai",
    "status": "grounded",
    "summary": "Compruebe primero conectividad, hora del sistema y estado del servicio simulado.",
    "steps": [
      {"order": 1, "text": "Confirme acceso a Internet sin la VPN.", "citation_ids": ["cit-01"]},
      {"order": 2, "text": "Consulte el estado de DemoVPN.", "citation_ids": ["cit-02"]}
    ],
    "warnings": ["No comparta credenciales ni códigos de un solo uso."],
    "citations": [
      {
        "id": "cit-01",
        "document_id": "8ae097e5-b280-4da4-bc84-c2403f20974d",
        "version": "1.0",
        "section": "2.1 Diagnóstico inicial",
        "chunk_id": "vpn-guide-1.0-002"
      }
    ],
    "review_status": "pending"
  }
}
```

Si la evidencia es insuficiente, se crea un recurso con `status: "abstained"`, pasos vacíos, razón y preguntas de seguimiento; no se responde con consejos generales inventados.

### 4.4 Consulta de herramienta

```json
{
  "tool": "service_status.get",
  "parameters": {"service_code": "demo_vpn"}
}
```

Respuesta:

```json
{
  "data": {
    "query_id": "e5ccfd13-2eab-4d69-bbd6-7670e1d81f40",
    "tool": "service_status.get",
    "status": "succeeded",
    "result": {"service_code": "demo_vpn", "state": "operational"},
    "simulated": true,
    "completed_at": "2026-10-27T18:32:00Z"
  }
}
```

`service_code` es un enum. URL, host y argumentos de proceso nunca son parámetros aceptados.

### 4.5 Propuesta, decisión y ejecución

Crear propuesta:

```json
{
  "action_type": "vpn_session.reset",
  "parameters": {"demo_user_id": "usr_demo_104"},
  "reason": "La guía y el diagnóstico indican una sesión simulada bloqueada.",
  "evidence_ids": ["cit-02", "e5ccfd13-2eab-4d69-bbd6-7670e1d81f40"]
}
```

Respuesta `201`:

```json
{
  "data": {
    "id": "0cbbbdca-d2a6-4c7b-a4ef-dc905706e385",
    "status": "pending",
    "sensitivity": "approval_required",
    "action_hash": "sha256:02b8...",
    "expires_at": "2026-10-27T19:03:00Z",
    "version": 1
  }
}
```

Decidir:

```json
{
  "decision": "approved",
  "comment": "Alcance y evidencia verificados para el usuario sintético."
}
```

La respuesta no permite cambiar parámetros. Ejecutar usa cuerpo vacío, `Idempotency-Key` e `If-Match`. Respuesta `202` mientras se ejecuta o `200` si el adaptador es síncrono y terminó dentro del presupuesto:

```json
{
  "data": {
    "id": "7cebc3f6-c1b3-43b9-8354-c64e80566a5e",
    "approval_request_id": "0cbbbdca-d2a6-4c7b-a4ef-dc905706e385",
    "status": "succeeded",
    "simulated": true,
    "result": {"code": "DEMO_SESSION_RESET", "changed": true},
    "completed_at": "2026-10-27T18:36:00Z"
  }
}
```

## 5. Catálogo inicial de herramientas

| Acción | Tipo | Parámetros | Aprobación | Efecto |
|---|---|---|---|---|
| `service_status.get` | Consulta | `service_code` enum | No | Lee estado sintético |
| `software_health.get` | Consulta | `application_code` enum | No | Lee salud sintética |
| `device_diagnostics.get` | Consulta | `demo_device_id` patrón estricto | No | Lee diagnóstico sintético |
| `vpn_session.reset` | Mutación | `demo_user_id` patrón estricto | Sí | Cambia estado de simulador |
| `software_config.repair` | Mutación | app y perfil demo | Sí | Simula reparación |
| `device_cache.cleanup` | Mutación | equipo demo, alcance enum | Sí | Simula limpieza sin archivos reales |
| `access_grant.apply` | Mutación | usuario/recurso/rol enums | Sí | Simula concesión |

No existe herramienta de shell, URL genérica, SQL, cambio de contraseña, borrado arbitrario o infraestructura.

## 6. Respuestas de error

Formato compatible conceptualmente con Problem Details:

```json
{
  "type": "https://opsbridge.local/problems/approval-required",
  "title": "Approval required",
  "status": 403,
  "code": "APPROVAL_REQUIRED",
  "detail": "This simulated action requires a valid approval.",
  "instance": "/api/v1/approval-requests/.../executions",
  "correlation_id": "35d27626-fc58-4557-b67a-f8ec514b4ced",
  "errors": []
}
```

| HTTP | Códigos principales | Uso |
|---|---|---|
| `400` | `MALFORMED_REQUEST` | JSON/formato no procesable antes de validación semántica |
| `401` | `AUTH_REQUIRED`, `SESSION_EXPIRED` | Sesión ausente/inválida |
| `403` | `FORBIDDEN`, `CSRF_INVALID`, `APPROVAL_REQUIRED`, `SEPARATION_OF_DUTIES` | Identidad conocida sin permiso |
| `404` | `RESOURCE_NOT_FOUND` | No existe o se oculta por control de acceso |
| `409` | `INVALID_TRANSITION`, `IDEMPOTENCY_CONFLICT`, `ALREADY_EXECUTED`, `APPROVAL_EXPIRED` | Conflicto con estado actual |
| `412` | `VERSION_MISMATCH` | `If-Match` obsoleto |
| `422` | `VALIDATION_ERROR`, `UNSUPPORTED_CATEGORY` | Campos válidos sintácticamente pero no por contrato |
| `429` | `RATE_LIMITED`, `AI_CAPACITY_LIMIT` | Límite local; puede incluir `Retry-After` |
| `502` | `SIMULATOR_BAD_RESPONSE`, `AI_BAD_RESPONSE` | Dependencia respondió contrato inválido |
| `503` | `DEPENDENCY_UNAVAILABLE`, `AI_PROVIDER_UNAVAILABLE` | Dependencia opcional/obligatoria no disponible |
| `504` | `DEPENDENCY_TIMEOUT`, `EXECUTION_STATUS_UNKNOWN` | Timeout; mutación no se reintenta sin reconciliar |

Los detalles no incluyen stack trace, query SQL, prompt o secreto. Errores de validación indican campo y regla sin reflejar contenido sensible completo.

## 7. Paginación, búsqueda y consistencia

Ejemplo:

`GET /api/v1/tickets?status=in_progress&priority=p2,p3&page_size=25&cursor=opaque`

```json
{
  "data": [],
  "meta": {
    "page_size": 25,
    "next_cursor": null,
    "has_more": false,
    "correlation_id": "..."
  }
}
```

El cursor 2.3B codifica estrictamente posición UTC e UUID, nunca SQL. No concede acceso: cada página reaplica identidad, alcance y filtros en SQL. Todavía no está firmado; cualquier manipulación inválida devuelve `400` y una posición válida manipulada solo altera navegación dentro del conjunto ya autorizado. Firmarlo o almacenarlo queda como endurecimiento previo a exposición no local. El conteo total se omite.

## 8. Versionado y evolución

- La versión mayor está en URL (`/api/v1`).
- Cambios aditivos compatibles no incrementan mayor: campos opcionales, nuevos endpoints o nuevos enum solo cuando clientes los toleran; enums críticos requieren coordinación.
- Eliminaciones, cambios de semántica o campos requeridos nuevos crean `/v2` o periodo de deprecación documentado.
- OpenAPI se guarda como artefacto y se compara para detectar breaking changes.
- Cliente TypeScript se genera o tipa desde OpenAPI; no duplica esquemas manualmente sin prueba.
- El adaptador Ollama tiene su propio contrato porque la API de Ollama no está estrictamente versionada.

## 9. Contratos entre componentes

Puertos mínimos en términos conceptuales:

```text
TicketRepository: get, list, add, save_with_version
UnitOfWork: begin, commit, rollback
Classifier: classify(ticket, taxonomy) -> ClassificationProposal
Retriever: search(query, filters, limit) -> EvidenceSet
RecommendationProvider: recommend(ticket, evidence) -> UntrustedRecommendation
ToolAdapter: query(command) / execute(command, idempotency_key) -> ToolResult
AuditSink: append(event)
Clock / IdGenerator: interfaces inyectables
```

El `Application Service` valida cualquier `UntrustedRecommendation` y nunca pasa una estructura de proveedor directamente al `ToolAdapter`.

## 10. Límites y pendientes de Fase 2

- Generar modelos exactos Pydantic y OpenAPI, y verificar todos los ejemplos.
- Definir TTL exactos después de pruebas UX/seguridad; valores aquí son iniciales.
- Elegir si las ejecuciones rápidas responden siempre `202` para uniformidad o `200/202`; documentarlo antes del frontend.
- Comprobar el mecanismo CSRF con la topología final de mismo origen.
- Formalizar scopes de visibilidad de comentarios y timeline.
