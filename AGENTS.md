# Instrucciones persistentes para OpsBridge AI

## Fuente de verdad

1. Leer `docs/PROJECT_STATE.md` antes de iniciar trabajo.
2. Consultar `docs/PRODUCT_REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, `docs/API_DESIGN.md` y `docs/SECURITY_AND_TESTING.md` según el módulo en alcance.
3. Trabajar únicamente en la fase expresamente autorizada por el responsable.
4. Actualizar `docs/PROJECT_STATE.md` al cerrar cada sesión con decisiones, evidencia, riesgos y siguiente paso.

## Restricciones permanentes

- No modificar DataTrust API ni otros proyectos.
- No publicar ni exponer servicios públicamente sin autorización explícita.
- No usar APIs comerciales pagadas ni datos personales reales.
- No conectar acciones a infraestructura, cuentas o equipos empresariales reales.
- No afirmar métricas, capacidades de IA, preparación para producción o experiencia profesional sin evidencia.
- El modo por reglas nunca debe presentarse como IA.
- La salida de un LLM es dato no confiable: validar esquema, permisos, evidencia y política antes de usarla.
- Las acciones sensibles requieren aprobación persistida, vigente y vinculada exactamente a la acción.
- Mantener simuladores en una frontera separada y denegar herramientas desconocidas.

## Forma de trabajo

- Preservar la arquitectura de monolito modular mientras no exista evidencia que justifique distribuir servicios.
- Preferir cambios pequeños con pruebas dirigidas; ejecutar suites completas en cierres de fase.
- No añadir LangGraph, una base vectorial externa, colas distribuidas ni Docker como dependencia obligatoria sin ADR y necesidad comprobada.
- Mantener contratos OpenAPI, modelos de dominio, migraciones y pruebas sincronizados.
- Usar datos sintéticos y semillas reproducibles.
- Documentar dependencias con lockfiles en la fase que las introduzca.
- Registrar decisiones relevantes como ADR en `docs/adr/` cuando comiencen a implementarse.
