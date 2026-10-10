# Lista y fichas con Gemma local Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Responder preguntas sobre lista y fichas observadas, registrar productos sin ficha para una futura investigación y añadir necesidades en español con Gemma 4 E2B, sin compras ni scraping nuevo.

**Architecture:** SQLite conserva la lista, observaciones fechadas y backlog. El código recupera contexto limitado antes de llamar a Ollama y valida su propuesta; construye respuestas sobre hechos estructurados y hace el registro del backlog junto con la respuesta duradera. Los comandos actuales siguen teniendo prioridad.

**Tech Stack:** Python 3.12, SQLite migraciones, Pydantic 2, httpx/Ollama `gemma4:e2b` (`num_ctx=4096`), pytest, Ruff, Windows/Telegram.

**Spec:** `docs/superpowers/specs/2026-09-29-lista-fichas-gemma-design.md`

## Global Constraints

- «Esta fase no incluye compras, preparación de carritos, histórico de pedidos, navegación nueva por tiendas ni scraping automático».
- «La lista describe el estado actual; cada ficha se presenta como observación histórica con fecha y fuente».
- «No incorporar datos personales ni HTML sin depurar»; «No registrar cuerpos de mensajes ni respuestas privadas de Ollama».
- «No afirmar cobertura de todas las tiendas, stock o precio actual, ni precio final con envío cuando se desconoce».
- «Un fallo o timeout de Ollama no crea pendientes ni mutaciones»; comandos deterministas siguen funcionando.
- «El modelo nunca inicia `buy`, `resume`, `remove` ni `set_quantity`»; mantener restricciones de fórmula, pienso y pañales, `live_verified=False`.
- «Esta especificación no autoriza cambios en el bot privado ni una publicación de rama»; sin push ni activación privada automática.

## Review Focus

1. Pregunta genérica («¿qué productos hay?») → no generar backlog vacío/genérico; test en Task 2.
2. Texto de producto que contiene instrucciones, URL ajena o negación → no convertirlo en orden, consulta inventada ni backlog; test en Task 2.
3. Repetición del mismo mensaje tras fallo entre backlog y respuesta → una sola solicitud y una sola respuesta duradera; test con inyección de fallo en Task 2.
4. Observación con stock/precio antiguo o GTIN solo en URL → fecha y límites visibles, ninguna modificación de catálogo/checkout; test en Task 1 y Task 2.
5. Modelo frío >60 s o respuesta JSON incompleta → aclaración, sin modificar datos y comandos disponibles; test en Task 3.

---

## Archivos e interfaces

- `product_memory.py`: `ObservedProduct` y observaciones estructuradas revisadas contra `docs/store-capabilities.md`; normalización de nombre/alias y búsqueda limitada. No contiene un scraper ni precios sin fecha.
- `migrations/005.sql`, `storage.py`: tablas `observed_products`, `product_requests` y API `Repository.find_products(query: str, limit: int = 5) -> list[ObservedProduct]`; `_record_missing_product(db, name: str)` se usa solo dentro de `apply_intent` para atomicidad. `migrate()` se puede repetir sin alterar lista/pedidos/offset.
- `domain.py`, `conversation.py`: nuevo `Intent.action='product_query'` con una sola `IntentLine(description=...)`; validar nombre íntegro anclado en el mensaje y no permitir campos/cantidades adicionales. `Repository._apply` responde con hechos en SQLite, o registra ausencia y responde sin ficha. `list` existente produce respuesta real de SQLite.
- `ollama_interpreter.py`: `parse(text, lines)` sigue funcionando; añadir `parse_with_context(text: str, lines: list[ListLine], products: list[ObservedProduct]) -> Intent` para preguntas libres. `Conversation` usa esta capacidad solo si el intérprete la ofrece; `OpenAIInterpreter` y fakes conservan la interfaz antigua. El contexto nunca incluye secretos ni fichas irrelevantes.
- `docs/setup.md` / `docs/superpowers/progress.md`: uso, fecha de fichas, límites, mediciones y estado real; no almacenar secretos, HTML o pesos en Git.

### Task 1: Fichas fechadas y backlog persistente

**Files:** crear `product_memory.py`, `migrations/005.sql`, `tests/test_product_memory.py`; modificar `storage.py`.

**Interfaces:** produce `ObservedProduct` inmutable con `id`, `store_id`, `product_id`, `title`, `url`, `observed_on`, `price_cents: int | None`, `availability: bool | None`, `format_note: str | None` y `Repository.find_products(query: str, limit: int = 5) -> list[ObservedProduct]`; produce `_record_missing_product(db, name: str) -> None` transaccional y `Repository.product_requests() -> list[str]` para supervisar backlog sin leer mensajes privados.

- [ ] **Step 1: Test RED.** Sembrar solo fichas revisadas: Amascotados Alpha Spirit Wild Fish 12 kg (2026-09-27, 6399 céntimos), Charro Blemil Optimum Evolution 1 800 g (2026-09-27, 2515 céntimos, referencia no verificada), Nappy Dodot talla 3 186 unidades (2026-09-27, 4687 céntimos), Mercadona Dodot Sensitive talla 3 paquete 56 (2026-09-28, 1695 céntimos); URL pública desde `docs/store-capabilities.md`. Tests: `migrate()` dos veces deja cuatro fichas y conserva lista/offset; búsqueda «pañales Dodot» devuelve ambas fichas relevantes, `limit=1` devuelve una; «arroz» ninguna; campos desconocidos siguen `None`; no se crea GTIN ni se cambia la tabla `products`. Backlog normalizado «Arroz»/«arroz» una sola fila con fecha, sin texto de mensaje. Migración desde v4 y DB nueva.
- [ ] **Step 2: Ejecutar RED.** `.venv\Scripts\python.exe -m pytest tests/test_product_memory.py -q` → falla por APIs/migración ausentes.
- [ ] **Step 3: Implementar.** Crear tabla con clave estable para fichas y backlog con nombre normalizado único; `Repository.migrate` hasta v5 con semillas `INSERT OR IGNORE`, sin mezclar fichas con `Offer` ejecutable. Búsqueda tokenizada/alias cerrado, acento-insensible, sin substring accidental, tope de resultados. Fechas de fuente explícitas.
- [ ] **Step 4: Ejecutar GREEN.** Misma orden y `.venv\Scripts\python.exe -m ruff check product_memory.py storage.py tests/test_product_memory.py` → PASS.
- [ ] **Step 5: Commit.** `git add product_memory.py migrations/005.sql storage.py tests/test_product_memory.py` y commit `feat: persist dated product observations and request backlog`.

### Task 2: Consulta y alta seguras sobre datos reales

**Files:** modificar `domain.py`, `conversation.py`, `storage.py`, `tests/test_conversation.py`; añadir `tests/test_product_queries.py`.

**Interfaces:** consume `Repository.find_products` y `_record_missing_product` de Task 1. Produce `Intent(action='product_query', lines=[IntentLine(description=<nombre>)])` y respuesta determinista dentro de `Repository.apply_intent`, con backlog y outbox en la misma transacción; preserva firmas de `Conversation.handle` y `Repository.apply_intent`.

- [ ] **Step 1: Test RED.** Con `FakeInterpreter`, «¿qué hay en mi lista?» → `list` y muestra líneas actuales después de reiniciar; «¿qué pañales Dodot vimos?» → `product_query` con dos fichas, fechas, fuente, precios observados y aviso de stock/precio no actuales; «¿qué sabes de arroz?» → respuesta sin ficha y backlog `arroz` una sola vez incluso tras reintento/reinicio. Pregunta genérica no crea backlog; texto con negación, citas, varios productos, URL, ID inventado, cantidad inventada o sustitución «pienso de pollo» → aclaración o rechazo sin cambios. Inyectar fallo SQLite al crear outbox: rollback de backlog y respuesta; reintento posterior crea exactamente una entrada y un aviso. Comandos `/lista` y `/anadir` no llaman al modelo.
- [ ] **Step 2: Ejecutar RED.** `.venv\Scripts\python.exe -m pytest tests/test_product_queries.py tests/test_conversation.py -q` → fallos por consulta de producto ausente.
- [ ] **Step 3: Implementar.** Ampliar Literal de `Intent` y validador en `Conversation`; recuperar instantánea de lista y fichas relevantes antes de inferencia solo en la ruta libre. Anclar el nombre consultado como tramo completo de una pregunta normalizada de formas cerradas (`qué sabes de <producto>`, `qué <producto> vimos`, `tenemos ficha de <producto>`); tolerar signos de interrogación, no recortar calificadores ni aceptar una subcadena del nombre. Sin coincidencia inequívoca, aclarar. `Repository._apply` formatea lista/fichas exclusivamente desde SQLite y registra backlog en la misma transacción de inbox/outbox; no llama a tiendas. Mantener los controles existentes de `add`.
- [ ] **Step 4: Ejecutar GREEN y regresión.** Tests específicos, luego `.venv\Scripts\python.exe -m pytest -q` y `.venv\Scripts\python.exe -m ruff check .` → PASS.
- [ ] **Step 5: Commit.** `git add domain.py conversation.py storage.py tests/test_conversation.py tests/test_product_queries.py` y commit `feat: answer list and product queries with durable backlog`.

### Task 3: Gemma contextual y prueba con modelo real

**Files:** modificar `ollama_interpreter.py`, `tests/test_ollama_interpreter.py`, `docs/setup.md`, `docs/superpowers/progress.md`.

**Interfaces:** consume `ObservedProduct` y `product_query` de Tasks 1–2. Produce `OllamaInterpreter.parse_with_context(text: str, lines: list[ListLine], products: list[ObservedProduct]) -> Intent`; `parse(text, lines)` delega con lista vacía. No se altera la URL fija `http://127.0.0.1:11434/api/chat`, `trust_env=False`, `follow_redirects=False`, timeout total 60 s, `think=False`, `num_ctx=4096`.

- [ ] **Step 1: Test RED.** Fake `httpx.MockTransport`: «necesito arroz» recibe instrucciones de lista de compras con ejemplo `add` sin cantidad; «¿qué hay en mi lista?» recibe descripciones/IDs mínimos de lista; «¿qué pañales vimos?» recibe como máximo cinco fichas fechadas y nunca token/dirección/historial ni HTML; modelo devuelve `product_query` o `list`, mientras `buy`/`remove` no pasan el validador. Timeout, rechazo, JSON truncado o redirección → `clarify`, sin HTTP a host externo; `/lista` elude el modelo.
- [ ] **Step 2: Ejecutar RED.** `.venv\Scripts\python.exe -m pytest tests/test_ollama_interpreter.py -q` → fallos por método/contexto ausentes.
- [ ] **Step 3: Implementar.** Prompt breve y específico del asistente de compras, ejemplos inequívocos de `add`, consulta de lista, consulta de ficha y negación; datos serializados como datos no fiables y esquema `Intent`. Sin herramientas, navegación ni acceso arbitrario a SQLite. Mantener validación en `Conversation`, no fiarse del prompt para seguridad.
- [ ] **Step 4: Ejecutar GREEN y prueba real no privada.** Tests específicos, suite completa y Ruff → PASS. Con el Ollama ya instalado y modelo local, pruebas aisladas sin datos privados (varios intentos de «necesito arroz», «¿qué hay en mi lista?», «¿qué pañales vimos?», «¿qué sabes de arroz?», «no compres»), comprobar resultado de `Conversation` con DB de prueba, registrar tiempos frío/caliente y `nvidia-smi`/`ollama ps`; si el modelo falla repetidamente, mantener deshabilitado y documentar bloqueo, no subir tamaño ni habilitar otro proveedor en silencio.
- [ ] **Step 5: Commit.** `git add ollama_interpreter.py tests/test_ollama_interpreter.py docs/setup.md docs/superpowers/progress.md` y commit `feat: give local Gemma bounded shopping context` (si solo cambia documentación, usar prefijo `docs:`).

### Task 4: Aceptación sin compras y entrega

**Files:** actualizar `docs/superpowers/progress.md` y `docs/setup.md` con evidencia observada; tests de integración en `tests/test_runtime.py` solo si se detecta hueco (usar systematic-debugging antes de corregir defectos).

**Interfaces:** usa `model-local enable|disable|status` existente, no crea nuevos comandos ni toca checkout.

- [ ] **Step 1: Test RED si hay código.** Reproducir con fake Telegram+SQLite reinicio/inbox/outbox y fallo Ollama sin mutar lista/backlog; si Task 3 ya cubre todo y solo resta aceptación manual, documentar que no hay cambio de código ni inventar RED.
- [ ] **Step 2: Prueba de aceptación condicionada.** Solo si calidad de Task 3 es suficiente y el usuario dispone de sesión privada: coordinar parada del worker, comprobar bloqueo y activar modelo sin copiar secretos a worktree. Probar en Telegram privado alta de arroz, lista, ficha observada, ausencia/backlog y reinicio; no ejecutar `/comprar` ni entrar en tiendas. Si falta sesión o calidad, no activar: consignar pendiente y comandos disponibles.
- [ ] **Step 3: Verificación final.** `.venv\Scripts\python.exe -m pytest -q`, `.venv\Scripts\python.exe -m ruff check .`, `git diff --check`, `git status --short` → documentar salidas reales, distinguir fakes de aceptación Telegram y límites de GPU.
- [ ] **Step 4: Commit y entrega.** Commit de evidencia/documentación; no hacer push sin autorización de publicación. Resumir resultado y bloqueos sin declarar Telegram validado si no se probó.

## Autoevaluación

Cobertura: esquema/migración/semillas y backlog en Task 1; reglas semánticas, atomicidad y respuestas en Task 2; contexto mínimo, modelo real y límites de tiempo en Task 3; aceptación privada condicionada y entrega en Task 4. Interfaces coinciden; todas las entradas de Review Focus tienen test asignado. No se prometen precios actuales, scraping autónomo ni compra. Task 4 no fuerza activación si Task 3 falla o no hay sesión privada.
