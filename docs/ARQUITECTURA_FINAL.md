# Arquitectura final verificada

## Contexto y contenedores

```mermaid
flowchart TB
  R[Solicitante] --> SPA[React SPA local]
  T[Técnico] --> SPA
  A[Aprobador] --> SPA
  SPA -->|HTTP loopback, cookie opaca, CSRF| API[FastAPI modular monolith]
  API --> DB[(SQLite + FTS5)]
  API --> SIM[Simulador VPN sintético]
  API -. no disponible .-> LLM[Ollama local pendiente]
```

No hay red corporativa, correo, SSO, nube, broker o herramienta de shell.

## Componentes backend

```mermaid
flowchart LR
  HTTP[Presentation routes/errors] --> APP[Application services]
  APP --> DOMAIN[Ticket domain]
  APP --> AUTH[Auth policy]
  APP --> KNOW[Knowledge retrieval]
  APP --> AUTO[Automation policy]
  DOMAIN --> PORTS[Repository/UoW ports]
  PORTS --> INFRA[SQLAlchemy adapters]
  AUTH --> INFRA
  KNOW --> ORM[(Knowledge ORM)]
  AUTO --> ORM2[(Automation ORM)]
```

Tickets conserva dominio e infraestructura separados. Knowledge/Automation acceden directamente a sus ORM como deuda P2 aceptada para el alcance pequeño; si crecen deben extraer puertos.

## Flujo transaccional de ticket

```mermaid
sequenceDiagram
  participant H as HTTP
  participant S as TicketService
  participant U as UnitOfWork
  participant D as Domain
  participant Q as SQLite
  H->>S: command + actor + If-Match
  S->>U: begin
  U->>Q: load ticket/events
  S->>D: validate and transition
  U->>Q: conditional update(version)
  U->>Q: append events/idempotency
  U-->>S: commit or rollback
  S-->>H: snapshot + ETag
```

## Estados

```mermaid
stateDiagram-v2
  [*] --> new
  new --> triaged
  new --> cancelled
  triaged --> in_progress
  triaged --> cancelled
  in_progress --> waiting_requester
  in_progress --> waiting_approval
  in_progress --> resolved
  waiting_requester --> in_progress
  waiting_requester --> cancelled
  waiting_approval --> in_progress
  waiting_approval --> resolved
  resolved --> closed
  resolved --> in_progress
```

El diagrama conserva todos los estados del núcleo de dominio. En el contrato HTTP de `v1.0.0-rc.1`, las aristas hacia y desde `waiting_approval` están deliberadamente cerradas: el servidor no acepta una confirmación booleana del cliente como prueba de aprobación. El flujo gobernado VPN usa propuestas persistidas, decisión independiente y revalidación de estado, asignación y versión antes de ejecutar.

## Aprobación y efecto

```mermaid
sequenceDiagram
  participant T as Técnico
  participant P as Policy server
  participant A as Aprobador distinto
  participant DB as SQLite
  participant S as VPN simulator
  T->>P: propose(ticket, version, DEMO identity)
  P->>DB: pending + canonical hash + expiry
  A->>P: approve(proposal)
  P->>DB: separation-of-duties check
  T->>P: execute(proposal)
  P->>DB: recheck actor/status/version/hash/expiry
  P->>DB: conditional claim approved → executed
  P->>S: synthetic reset
  P->>DB: execution + audit atomically
```

## Permisos resumidos

| Recurso | Solicitante | Técnico | Aprobador |
|---|---|---|---|
| Tickets | propios, crear/transiciones permitidas | todos, modificar/transicionar | lectura global |
| Knowledge | documentos autorizados | autorizados, incluido técnico | autorizados |
| Propuestas | no | crear/listar propias/ejecutar aprobadas | listar/decidir |
| Simulador | no | consulta/ejecución gobernada | consulta, no ejecución |

## Amenazas y controles

```mermaid
flowchart TD
  U[Input no confiable] --> V[Schema + límites]
  D[Documento adversarial] --> R[FTS5 como datos + role scope]
  M[Salida futura de modelo] --> V
  V --> P[RBAC + propiedad + allowlist]
  P --> H[Human approval bound to hash/version/expiry]
  H --> C[Conditional exactly-once claim]
  C --> S[Synthetic simulator]
  S --> A[Local audit]
```

Controles adicionales: Argon2id, cookie HttpOnly/SameSite, token CSRF derivado, Origin exacto, rate limit, 404 uniforme, RFC 9457 sin trazas, FK/WAL/busy timeout, ETag e idempotencia. Límites: auditoría mutable local, SQLite single-writer y LLM no verificado.
