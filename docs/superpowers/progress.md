# Progreso del asistente de compras

## Diseño arquitectónico
- [x] Explorar el proyecto: carpeta vacía, sin repositorio Git.
- [x] Aclarar objetivo, productos restringidos y alojamiento en Windows.
- [x] Evaluar enfoque: conexiones verificadas con tiendas frente a navegación abierta; seleccionado el primero.
- [x] Presentar arquitectura y flujo; aprobados en conversación.
- [x] Evaluar apoyo visual: no necesario para las decisiones actuales.
- [x] Escribir especificación.
- [x] Revisar coherencia, alcance, ambigüedad y requisitos de la especificación.
- [x] Obtener aprobación del documento escrito.
- [x] Preparar el plan con writing-plans después de esa aprobación.
- [x] Revisar cobertura de la especificación e interfaces del plan.
- [x] Obtener revisión del plan y elección del método de ejecución.

Git fue inicializado antes de la tarea 1; base de implementación: `50da498`.

## 2026-09-27 — Task 1: persistence and catalog

- Installed official CPython 3.12.10 per-user after validating the installer Authenticode
  signature (Python Software Foundation); no administrator installation or PATH changes.
- Created `.venv`, strict domain contracts, private configuration, catalog restrictions,
  and SQLite migration/repository with transactional inbox, offset, immutable orders,
  versioned list, outbox, and foundations for suborders/attempts/events.
- Formula remains unverified, with no invented GTIN or weight. No purchases attempted.
- TDD: initial missing-module collection failure; database immutability test also failed
  before adding order-level guards. Final verification recorded in task report.
- Repository is source/editable-install oriented. Later tasks own conversation, transport,
  orchestration, browser, store operations, and durable suborder transitions.
