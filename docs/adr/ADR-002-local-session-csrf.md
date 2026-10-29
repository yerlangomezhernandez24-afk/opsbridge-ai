# ADR-002 — Sesión local opaca y protección CSRF

**Estado:** aceptada en Fase 2.3A  
**Fecha:** 2026-10-28

## Contexto

OpsBridge AI necesita autenticación reproducible para una demo local sin proveedor externo, sin exponer credenciales al frontend y sin convertir SQLite en un sistema de identidad empresarial. El contrato aprobado exige cookie `HttpOnly`, rotación frente a fijación, expiración, revocación, CSRF y CORS restringido.

## Decisión

- Las contraseñas se almacenan con Argon2id (`time_cost=3`, `memory_cost=65536 KiB`, `parallelism=4`, hash de 32 bytes y sal de 16 bytes).
- El login emite 32 bytes aleatorios con representación URL-safe. La base solo guarda su verificador SHA-256; la entropía del token, no una contraseña humana, evita búsqueda práctica.
- La cookie se llama `opsbridge_session`, es `HttpOnly`, `SameSite=Lax`, de ruta `/` y `Secure` con TLS. El perfil HTTP local permite `Secure=false` porque configuración y servidor rechazan hosts no loopback.
- La sesión tiene expiración absoluta de 8 horas e inactividad de 30 minutos por defecto. Se valida usuario activo, revocación y ambas expiraciones en cada uso.
- Un login rota la sesión presentada. Logout revoca de forma persistente.
- El CSRF se deriva del token de sesión con un hash separado por dominio y se compara en tiempo constante. No se persiste ni se coloca en `localStorage`; `/api/v1/auth/session` lo entrega con `Cache-Control: no-store`.
- Login y logout exigen coincidencia exacta con un único `Origin` configurado. Logout exige además `X-CSRF-Token`. Login no usa pre-sesión CSRF para evitar una cookie anónima adicional.
- CORS permite credenciales únicamente para ese origen exacto; no se permiten comodines.
- El límite de intentos es local al proceso: cinco fallos en cinco minutos, bloqueo de cinco minutos. No se presenta como protección distribuida.

## Consecuencias

La sesión sobrevive reinicios y puede revocarse, mientras el token utilizable nunca se guarda en SQL ni en respuestas JSON. La estrategia sirve para la demo local, pero no sustituye SSO/MFA, un rate limiter compartido, gestión empresarial de identidades ni protección frente a un administrador local con control total del proceso. Un despliegue no local requeriría TLS, revisión del modelo de amenazas y probablemente un proveedor de identidad dedicado.
