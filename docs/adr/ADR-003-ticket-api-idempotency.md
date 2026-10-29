# ADR-003 — Idempotencia persistente para creación de tickets

**Estado:** aceptada en Fase 2.3B  
**Fecha:** 2026-10-28

## Contexto

Una creación HTTP puede repetirse por doble envío, timeout o reintento del cliente. Un diccionario en memoria no sobrevive reinicios, no coordina conexiones y puede filtrar resultados entre usuarios.

## Decisión

- `Idempotency-Key` es un UUID v4 canónico obligatorio para `POST /api/v1/tickets`.
- El alcance único es `(user_id, operation, key)`; usuarios distintos pueden usar la misma clave sin compartir resultados.
- La huella SHA-256 se calcula sobre JSON canónico de título/descripcion normalizados, categoría, impacto y urgencia. No incluye cookies, sesión, CSRF o contraseñas.
- Una reserva SQLite `INSERT ... ON CONFLICT DO NOTHING RETURNING` ocurre dentro de la misma Unit of Work que asigna la clave pública, inserta ticket/evento y completa el registro.
- Se persisten ticket resultante e instantánea JSON saneada de la respuesta inicial. Una repetición idéntica reproduce esa instantánea aun si el ticket cambió después; una carga diferente devuelve `409`.
- La retención inicial es 24 horas. Registros expirados se eliminan oportunistamente al crear; no existe todavía un proceso de limpieza en segundo plano.
- Rollback elimina reserva, ticket, evento y contador como una sola transacción. No se afirma “exactly once” fuera de esta base y operación.

## Consecuencias

La política sobrevive reinicios y evita duplicados en las carreras comprobadas con SQLite. Aumenta el almacenamiento temporal y depende del límite de un escritor de SQLite. Una fase futura puede añadir limpieza programada y ampliar idempotencia a otros comandos solo cuando sus contratos estén definidos.
