# Informe técnico — Fase 2.1: dominio de tickets

**Proyecto:** OpsBridge AI  
**Responsable:** Yerlan Daniel Gómez Hernández  
**Fecha de cierre:** 2026-10-28  
**Estado:** **GO técnico**, pendiente de revisión del responsable

## 1. Alcance ejecutado

Se implementó exclusivamente el núcleo de dominio de tickets, sin dependencias de FastAPI, Pydantic, SQLAlchemy ni servicios externos:

- agregado `Ticket` con identidad UUID v4, clave humana, contenido validado, categoría, impacto, urgencia, prioridad, estado, fechas UTC, solicitante, asignación y versión;
- vocabularios cerrados para estados, categorías, prioridades, impacto, urgencia y roles;
- política determinista y versionada `impact-urgency-v1`;
- máquina de estados explícita con reglas de actor y precondiciones;
- operaciones controladas de categoría y reevaluación de prioridad;
- control de concurrencia mediante `version` y `expected_version`;
- eventos inmutables mínimos de creación, categoría, prioridad, asignación, estado, resolución y cierre;
- errores de dominio tipados, sin semántica HTTP;
- 133 pruebas unitarias nuevas, además de las 14 pruebas de regresión existentes.

No se crearon endpoints, tablas, modelos SQLAlchemy, migraciones empresariales, repositorios, autenticación, infraestructura RBAC, frontend, RAG, IA ni agentes.

## 2. Decisiones mínimas cerradas

### 2.1 Taxonomía

La ambigüedad existente entre `hardware.endpoint` y `endpoint.performance` se resolvió usando **`hardware.endpoint`** como categoría canónica. Se corrigió la mención ambigua en `PRODUCT_REQUIREMENTS.md`; no se rediseñó la taxonomía.

Categorías iniciales:

- `network.vpn`
- `software.application`
- `hardware.endpoint`
- `access.application`

### 2.2 Prioridad determinista

La prioridad nunca se recibe como autoridad externa: se deriva de impacto y urgencia. La política se identifica como `impact-urgency-v1` y conserva el ejemplo contractual `single_user + medium = p3`.

| Impacto \ Urgencia | `low` | `medium` | `high` |
|---|---:|---:|---:|
| `single_user` | `p4` | `p3` | `p3` |
| `multiple_users` | `p4` | `p3` | `p2` |
| `organization` | `p3` | `p2` | `p1` |

Una reevaluación con impacto o urgencia distintos genera revisión y evento aunque permanezca en la misma banda de prioridad. Repetir exactamente las mismas entradas es idempotente.

### 2.3 Identidad, tiempo y concurrencia

- El identificador interno debe ser UUID v4.
- La clave debe seguir `OPS-YYYY-NNNNNN` y su año debe coincidir con `created_at`.
- Los IDs y tiempos se reciben desde el exterior del agregado, lo que permite reloj y generador controlados en pruebas y futura aplicación.
- Todas las fechas deben ser conscientes de zona y estar en UTC; no se admite retroceder respecto de `updated_at`.
- Cada operación efectiva incrementa una sola revisión. Los eventos atómicos de una misma operación comparten revisión.
- `expected_version` detecta escrituras obsoletas sin modificar el agregado.

### 2.4 Auditoría segura

El historial es una tupla de eventos inmutables. Los eventos contienen identidad, actor, hora, revisión y el cambio estructurado necesario. No duplican título, descripción, resumen de resolución ni razones libres, reduciendo exposición y retención innecesaria de contenido potencialmente sensible.

## 3. Máquina de estados verificada

Estados implementados: `new`, `triaged`, `in_progress`, `waiting_approval`, `waiting_requester`, `resolved`, `closed` y `cancelled`.

Transiciones normales:

| Desde | Hacia | Regla principal |
|---|---|---|
| `new` | `triaged` | técnico; automatización solo con clasificación validada |
| `triaged` | `in_progress` | técnico y asignación explícita |
| `in_progress` | `waiting_approval` | técnico y referencia de aprobación |
| `waiting_approval` | `in_progress` | técnico, aprobador o automatización; aprobación resuelta/expirada |
| `in_progress` | `waiting_requester` | técnico y razón documentada |
| `waiting_requester` | `in_progress` | solicitante propietario y respuesta registrada |
| `in_progress` | `resolved` | técnico y resumen de resolución |
| `resolved` | `in_progress` | técnico y razón de reapertura |
| `resolved` | `closed` | confirmación del solicitante o razón de cierre del técnico |

Además, cualquier estado no terminal puede pasar a `cancelled`: el solicitante propietario solo antes de iniciar trabajo (`new` o `triaged`), o un técnico con razón documentada. `closed` y `cancelled` son terminales. Repetir el estado actual es una operación idempotente sin evento ni incremento de versión.

La matriz completa de 8 × 8 quedó cubierta:

- 15 transiciones permitidas;
- 41 transiciones prohibidas;
- 8 repeticiones idempotentes;
- **64/64 pares verificados**.

## 4. Archivos creados o modificados

Código de dominio:

- `backend/src/opsbridge/domain/tickets/__init__.py`
- `backend/src/opsbridge/domain/tickets/enums.py`
- `backend/src/opsbridge/domain/tickets/errors.py`
- `backend/src/opsbridge/domain/tickets/events.py`
- `backend/src/opsbridge/domain/tickets/priority.py`
- `backend/src/opsbridge/domain/tickets/ticket.py`
- `backend/src/opsbridge/domain/tickets/values.py`

Pruebas:

- `backend/tests/__init__.py`
- `backend/tests/unit/__init__.py`
- `backend/tests/unit/domain/__init__.py`
- `backend/tests/unit/domain/support.py`
- `backend/tests/unit/domain/test_priority_and_creation.py`
- `backend/tests/unit/domain/test_transitions.py`
- `backend/tests/unit/domain/test_events_and_updates.py`
- `backend/scripts/test.ps1` (corrección para detenerse ante códigos de salida no cero)

Documentación:

- `docs/PRODUCT_REQUIREMENTS.md`
- `docs/PROJECT_STATE.md`
- `docs/FASE_2_1_DOMINIO_TICKETS.md`

No se modificó `pyproject.toml`, `requirements.lock`, Alembic, la presentación HTTP ni la infraestructura SQL.

## 5. Entorno y versiones realmente usadas

| Componente | Versión verificada |
|---|---:|
| Python | 3.12.14 |
| pytest | 9.2.0 |
| Ruff | 0.17.3 |
| mypy | 2.4.0 |
| pluggy | 1.7.0 |

Se utilizó el entorno virtual existente de Fase 2.0. No se instalaron dependencias ni se cambió el lockfile. Python 3.11 no está instalado en este equipo y permanece pendiente de verificación real.

## 6. Comandos y resultados

Línea base antes de cambios:

```powershell
cd <PROJECT_ROOT>\backend
.\scripts\test.ps1
```

Resultado: Ruff, formato y mypy aprobados; 14 pruebas aprobadas; `pip check` limpio.

Construcción y comprobaciones específicas:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\opsbridge\domain\tickets tests\unit\domain
.\.venv\Scripts\python.exe -m mypy src\opsbridge\domain\tickets tests\unit\domain
.\.venv\Scripts\python.exe -m pytest tests\unit\domain -q
```

Resultado específico tras el cierre de invariantes: 133 pruebas aprobadas. Durante la construcción, mypy detectó anotaciones faltantes en atributos con `__slots__` y Ruff detectó formato/orden; ambos defectos se corrigieron antes del cierre. No hubo pruebas unitarias fallidas.

Suite final:

```powershell
.\scripts\test.ps1
```

Resultado final:

```text
Ruff: All checks passed
Ruff format: 42 files already formatted
mypy --strict: Success, 39 source files
pytest: 147 passed in 0.95s
pip check: No broken requirements found
```

La primera corrida completa posterior a la implementación encontró dos errores de orden de imports/`__all__` en Ruff. Esa corrida reveló que el script heredado seguía ejecutando herramientas después de un código de salida no cero. Se corrigió `test.ps1` para validar cada proceso, se añadió una comprobación explícita de que `status` no admite asignación pública y se repitió toda la suite con el resultado limpio anterior.

## 7. Criterios de aceptación

| Criterio | Evidencia | Estado |
|---|---|---|
| Dominio sin framework | imports limitados a biblioteca estándar y paquete de dominio | Aprobado |
| Identidad y validaciones | UUID v4, clave humana, longitudes, UTC | Aprobado |
| Prioridad determinista | 9 combinaciones de matriz y versión de política | Aprobado |
| Transiciones exhaustivas | 64/64 pares de estados | Aprobado |
| Roles y precondiciones | pruebas por transición y actor | Aprobado |
| Idempotencia | estado, categoría y prioridad repetidos sin mutación | Aprobado |
| Auditoría mínima | eventos inmutables y sin contenido libre duplicado | Aprobado |
| Regresión del bootstrap | 14/14 pruebas previas dentro de la suite final | Aprobado |
| Calidad estática | Ruff, formato y mypy estricto | Aprobado |
| Dependencias | sin cambios y `pip check` limpio | Aprobado |
| Script de verificación | detención explícita por código de salida | Aprobado |
| Corte de alcance | sin API, SQL, migraciones, auth, IA ni frontend | Aprobado |

## 8. Limitaciones y pendientes

1. La secuencia `NNNNNN` de la clave humana todavía debe asignarse transaccionalmente en persistencia.
2. No existe rehidratación desde filas/eventos ni repositorio; corresponde a Fase 2.2.
3. Las razones y evidencias se validan como presencia de texto, pero su modelo persistente y política de retención aún no existen.
4. La política de cierre técnico se limita a exigir una razón; el plazo/configuración concreta debe definirse antes de exponer el caso de uso.
5. La autorización implementada es una invariante mínima por rol y pertenencia del solicitante, no un sistema RBAC.
6. Python 3.11 no fue ejecutado en este entorno.
7. La carpeta continúa sin ser repositorio Git; no se publicó nada.

## 9. Recomendación para Fase 2.2

Proceder solo tras revisión explícita. La siguiente fase debería implementar el mapeo SQLAlchemy, repositorio y migración inicial de tickets/eventos, generación transaccional de la clave legible, rehidratación del agregado y pruebas de rollback/bloqueo optimista. Debe reutilizar este dominio como autoridad y detenerse antes de endpoints, autenticación, RAG, IA o frontend.

**Conclusión:** no existe defecto crítico abierto dentro del alcance de Fase 2.1. El cierre es **GO técnico**.
