# ADR-001 — Persistencia transaccional de tickets en SQLite

**Estado:** Aceptada  
**Fecha:** 2026-10-28  
**Alcance:** Fase 2.2

## Contexto

El dominio de Fase 2.1 es independiente de frameworks, conserva historial y utiliza versión optimista. La Fase 2.2 necesita persistir el agregado en SQLite sin trasladar SQLAlchemy al dominio, sin perder eventos y sin usar una clave pública basada en `MAX()+1`.

SQLite es la base local aprobada. Sus escritores se serializan y no representa una promesa de carga multiusuario empresarial.

## Decisión

1. Separar registros SQLAlchemy, mapeadores y agregado de dominio.
2. Persistir tres tablas:
   - `tickets`: proyección actual y versión del agregado;
   - `ticket_events`: historial ordenado y con FK al ticket;
   - `ticket_key_sequences`: siguiente secuencia por año.
3. Hacer explícita la transacción mediante `SqlAlchemyUnitOfWork`; los repositorios nunca confirman por sí solos.
4. Insertar el ticket padre con `flush` antes de añadir sus eventos, manteniendo ambos en la misma transacción.
5. Asignar claves con un único `INSERT ... ON CONFLICT DO UPDATE ... RETURNING` dentro de la transacción. La unicidad también queda protegida por constraint.
6. Actualizar tickets con `UPDATE ... WHERE id = ? AND version = ?`. Cero filas afectadas distingue registro ausente de conflicto optimista.
7. Habilitar `foreign_keys`, WAL para bases de archivo y `busy_timeout` acotado. Un bloqueo SQLite produce un error distinto del conflicto de versión.
8. Rehidratar mediante `Ticket.rehydrate`, que no crea eventos y vuelve a validar identidad, prioridad, UTC, versión e historial.

## Consecuencias

- Ticket, eventos y contador confirman o revierten juntos.
- Dos actualizaciones basadas en la misma versión no pueden sobrescribirse silenciosamente.
- La numeración es única en las condiciones verificadas. No se promete ausencia permanente de huecos ante futuras integraciones o mantenimiento manual.
- La tabla local de eventos mejora trazabilidad, pero no es inmutable frente a un administrador del archivo SQLite.
- Un único escritor a la vez y los bloqueos siguen siendo límites reales de SQLite; una evolución a PostgreSQL requerirá otro adaptador y una decisión explícita.
- Usuarios, sesiones, comentarios, idempotencia HTTP y semillas funcionales no se incluyen: el prompt de Fase 2.2 limita esta implementación al agregado de tickets y la autenticación pertenece a Fase 2.3.
