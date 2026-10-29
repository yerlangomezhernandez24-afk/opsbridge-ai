# Informe técnico — Fase 2.2: persistencia y migraciones

**Proyecto:** OpsBridge AI  
**Responsable:** Yerlan Daniel Gómez Hernández  
**Fecha de cierre:** 2026-10-28  
**Estado:** **GO técnico**, pendiente de revisión del responsable

## 1. Resultado

Se conectó el dominio de tickets con SQLAlchemy 2.1 y SQLite mediante una frontera de persistencia explícita. El dominio continúa sin imports de SQLAlchemy, FastAPI o Pydantic. No se implementaron endpoints, autenticación, RBAC de infraestructura, frontend, IA ni integraciones.

Componentes entregados:

- contratos mínimos de repositorio, asignador de clave y Unit of Work en la capa de aplicación;
- registros ORM separados del agregado;
- mapeo bidireccional y rehidratación sin eventos artificiales;
- repositorio por UUID y clave pública;
- Unit of Work con commit explícito y rollback seguro;
- persistencia atómica del ticket, sus eventos y el contador de clave;
- actualización condicional por versión;
- errores distinguibles para ausencia, duplicado, conflicto, integridad, transacción, bloqueo y corrupción;
- migración inicial reproducible;
- configuración SQLite con FK, WAL en archivos y timeout acotado;
- pruebas de integración con archivos temporales reales.

## 2. Modelo relacional

| Tabla | Responsabilidad | Restricciones principales |
|---|---|---|
| `tickets` | Proyección actual del agregado | UUID PK, clave única, enums cerrados, versión positiva, orden temporal |
| `ticket_events` | Historial ordenado | FK restrictiva, orden único por ticket, tipo/rol cerrados, revisión positiva |
| `ticket_key_sequences` | Contador anual | año PK, rango del siguiente valor |

No se añadieron usuarios, sesiones, comentarios o idempotencia HTTP: la autorización y la API pertenecen a Fase 2.3. Tampoco se creó una semilla funcional porque el alcance autorizado exige persistencia del agregado y prohíbe adelantar módulos empresariales posteriores.

Los eventos almacenan solo los campos estructurados que ya existen en los eventos de dominio. No duplican título, descripción, resumen de resolución ni razones libres.

## 3. Transacciones y rehidratación

`SqlAlchemyUnitOfWork` abre una sesión, expone repositorio/asignador y solo confirma con `commit()`. Salir sin confirmar o recibir una excepción ejecuta rollback. El repositorio utiliza `flush` para insertar el ticket padre antes de sus eventos, pero nunca hace commit.

La rehidratación usa `Ticket.rehydrate` y conserva identidad, contenido, categoría, prioridad, impacto, urgencia, estado, fechas UTC, actores, resolución, versión e historial. Vuelve a validar:

- UUID v4 y formato/año de la clave;
- categoría, estado, impacto y urgencia;
- prioridad derivada por la política activa;
- timestamps UTC y ordenados;
- versión positiva;
- evento de creación inicial, revisiones y pertenencia al ticket.

Datos desconocidos o corruptos producen `CorruptPersistenceDataError`; no se sustituyen por valores predeterminados.

## 4. Claves legibles

La clave conserva `OPS-YYYY-NNNNNN`. Un único statement SQLite:

```text
INSERT ... ON CONFLICT(year) DO UPDATE ... RETURNING
```

asigna el valor dentro de la misma transacción que crea el ticket y sus eventos. La tabla `tickets` añade una restricción de unicidad. La estrategia no consulta `MAX(id)`.

Evidencia: ocho hilos sincronizados crearon ocho tickets y obtuvieron exactamente ocho claves distintas del rango `OPS-2026-000001` a `OPS-2026-000008`. También se verificó que un rollback libera la asignación no confirmada y que cada año usa su propio espacio.

No se implementaron reintentos. SQLite serializa escritores y el timeout es finito. No se promete ausencia futura de huecos ni más de 999999 claves por año.

## 5. Concurrencia optimista y bloqueos

Las actualizaciones ejecutan:

```text
UPDATE tickets SET ... WHERE id = :id AND version = :expected_version
```

Si no se afecta una fila, el repositorio comprueba si el registro existe y distingue `TicketNotFoundError` de `TicketVersionConflictError`.

Prueba ejecutada: dos agregados recuperados desde versión 1 realizaron cambios diferentes. El primero confirmó versión 2; el segundo fue rechazado. La lectura final conservó exclusivamente el primer cambio y dos eventos, sin sobrescritura silenciosa.

Un `BEGIN IMMEDIATE` controlado mantuvo un bloqueo de escritura; otro Unit of Work con timeout de 50 ms recibió `DatabaseLockedError`, no un conflicto de versión. No se oculta ni reintenta infinitamente el bloqueo.

## 6. Migración Alembic

Revisión: `0001_ticket_persistence`.

La prueba de migración creó un archivo vacío, ejecutó `upgrade head`, inspeccionó tablas, columnas, FK e índice, ejecutó `alembic check` sin diferencias y aplicó `downgrade base`. El downgrade se ejecutó exclusivamente sobre una base temporal desechable.

Comandos documentados desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic history
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```

No se ejecutaron migraciones sobre la base local predeterminada ni se borraron datos del usuario. La revisión no contiene rutas absolutas.

## 7. Pruebas y análisis estático

Línea base antes de cambios:

```text
147 passed in 0.60s
Ruff: aprobado
Ruff format: aprobado
mypy strict: 39 archivos aprobados
pip check: limpio
```

Pruebas dirigidas finales:

```text
21 passed in 2.78s
```

Suite final:

```powershell
.\scripts\test.ps1
```

```text
Ruff: All checks passed
Ruff format: 60 files already formatted
mypy --strict: Success, 56 source files
pytest: 168 passed in 3.61s
pip check: No broken requirements found
```

Resultado final: **168 aprobadas, 0 fallidas**. Las 147 pruebas anteriores continúan aprobadas.

Durante la construcción, la primera corrida dirigida encontró 11 fallos causados por el orden de inserción ORM: los eventos se intentaban escribir antes que el ticket padre. Se corrigió insertando el padre mediante `flush` dentro de la misma transacción, sin commit. También se eliminó un uso de API `flush(objects=...)` marcado como obsoleto y una corrida de cierre detectó una línea sin formato, corregida antes de repetir la suite. Después de las correcciones, las 21 pruebas dirigidas y la suite completa quedaron limpias.

Cobertura nueva relevante:

- creación/lectura por UUID y clave;
- recuperación tras cerrar conexiones;
- actualización y rehidratación de estado, prioridad, categoría, asignación, resolución e historial;
- ausencia, duplicado y corrupción controlados;
- commit, rollback y atomicidad;
- conflicto optimista y ausencia de eventos rechazados;
- ocho asignaciones concurrentes de clave;
- bloqueo SQLite distinguible;
- FK y WAL habilitados;
- upgrade, equivalencia con metadata, constraints y downgrade temporal.

## 8. Versiones verificadas

| Componente | Versión |
|---|---:|
| Python | 3.12.14 |
| SQLite | 3.53.1 |
| SQLAlchemy | 2.1.6 |
| Alembic | 1.20.1 |
| pytest | 9.2.0 |
| Ruff | 0.17.3 |
| mypy | 2.4.0 |

No se instalaron paquetes ni se modificaron `pyproject.toml` o `requirements.lock`. Python 3.11 sigue sin estar disponible para ejecución real.

## 9. Archivos principales creados o modificados

- `backend/src/opsbridge/application/ports/`
- `backend/src/opsbridge/domain/tickets/ticket.py`
- `backend/src/opsbridge/infrastructure/db/`
- `backend/alembic/env.py`
- `backend/alembic/versions/0001_ticket_persistence.py`
- `backend/tests/integration/persistence/`
- `backend/README.md`
- `backend/.env.example`
- `docs/adr/ADR-001-ticket-persistence-sqlite.md`
- `docs/PROJECT_STATE.md`
- `docs/FASE_2_2_PERSISTENCIA_MIGRACIONES.md`

## 10. Limitaciones y riesgos

1. SQLite admite un único escritor efectivo; las pruebas demuestran corrección local, no capacidad empresarial masiva.
2. WAL y timeout reducen fricción, pero no eliminan bloqueos.
3. La tabla de eventos no es un registro inmutable frente a administradores del archivo.
4. No hay reintentos automáticos; una futura política deberá ser limitada y distinguir operaciones seguras.
5. La secuencia anual tiene límite 999999 y no promete ausencia de huecos.
6. El downgrade solo se validó en datos desechables.
7. Python 3.11 y PostgreSQL no fueron probados.
8. Idempotencia HTTP, usuarios, sesiones, RBAC y ETag aún no existen.
9. No se migró una base de usuario real, por decisión de seguridad.

## 11. Criterios y recomendación

Todos los criterios esenciales de Fase 2.2 quedaron verificados: round-trip, rehidratación, transacción, versión, claves, eventos, migración, regresión y análisis estático.

La recomendación es autorizar separadamente la Fase 2.3 para autenticación local, RBAC y API de tickets. Esa fase debe reutilizar esta Unit of Work, mapear conflictos a Problem Details, incorporar ETag/`If-Match` e idempotencia y probar propiedad/roles. No debe iniciar frontend, RAG, agentes ni integraciones.

**Conclusión: GO técnico. No se inicia Fase 2.3 sin revisión.**
