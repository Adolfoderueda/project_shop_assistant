# Progreso del asistente de compras

**Punto de continuación (01-10-2026):**
`docs/superpowers/continuacion-gemma-2026-10-01.md` registra la corrección de los
dos defectos del handoff anterior. Suite: 371 tests pasan; Ruff limpio.
`docs/superpowers/prueba-gemma-2026-10-01.md` conserva dos pruebas aisladas con
Ollama real y límites observados. La calidad de clasificación sigue pendiente,
al igual que la aceptación en Telegram; no considerarlo listo para uso habitual.

**Seguimiento solicitado por el usuario:** quiere probar Telegram experimentalmente.
Se corrigió el atasco de `model-local enable` por procesos ACL por archivo; ahora
se aplica/verifica por lotes sin relajar los permisos. **379 tests pasan**, Ruff
limpio. Activación en configuración temporal con 728 archivos/236 carpetas de
perfiles: 23,898 s; no es prueba del bot privado. Ver el seguimiento del documento
de continuación y las instrucciones de worktree en `docs/setup.md`.

## 2026-09-29 — Aceptación sin compras (Task 4; PENDIENTE EN TELEGRAM)

- La prueba pequeña de Task 3 usó Ollama real y SQLite aislada, no la sesión Telegram
  privada. La corrección permitió dos altas independientes de «necesito arroz» sin
  cantidad; el resultado no acredita fiabilidad general, ni latencia/VRAM máximas.
  El fallo anterior de «necesito arroz» ocurrió antes de esa corrección. `docs/setup.md`
  distingue ambos resultados y describe un protocolo de aceptación condicionado.
- No hay acceso autorizado a configuración privada, sesión Telegram ni activación del
  bot; no se paró el worker ni se ejecutó `model-local enable`, `disable` o `status`
  contra el bot privado. No hubo tiendas, scraping, `/comprar`, compras ni push.
  La aceptación en Telegram, reinicio real, persistencia de inbox/outbox en esa sesión
  y fallo de Ollama con el bot vinculado siguen **pendientes**. Hasta obtener autorización
  y sesión disponible, conservar el proveedor sin cambios y usar comandos explícitos.
- Cobertura offline existente: pruebas de flujo de backlog/reinicio/inbox/outbox y
  pruebas de fallo Ollama sin fallback y continuidad de comandos; no sustituyen una
  prueba integrada de Telegram privado. No se observó defecto que requiriese cambiar
  código o añadir un RED artificial; Task 4 cambia solo documentación.
- Verificación de esta rama: `.venv\Scripts\python.exe -m pytest -q` → **329 passed
  in 134.53s**; `.venv\Scripts\python.exe -m ruff check .` → **All checks passed!**;
  `git diff --check` → limpio (avisos de conversión LF→CRLF para ambos documentos);
  `git status --short` antes del commit → `M docs/setup.md`, `M docs/superpowers/progress.md`.
  Estas pruebas usan dobles para Telegram, no constituyen aceptación live.

## 2026-09-29 — Intérprete local contextual (Task 3)

- Gemma 4 E2B recibe texto, instantánea mínima de lista y hasta cinco fichas pertinentes
  fechadas, sin URL de fichas ni identificadores internos; comandos deterministas eluden
  Ollama. `Conversation` mantiene la validación y responde desde SQLite.
- TDD RED 5 fallos de contexto/dispatch; otro RED de prioridad `necesito` tras la primera
  prueba real. GREEN enfocados 94 passed; suite 329 passed; Ruff limpio.
- Ollama real con DB aislada y textos inventados: primera carga 11,34 s; caliente
  0,39–0,67 s. Tras reforzar prioridad, dos peticiones independientes «necesito arroz»
  añadieron una línea sin cantidad cada una; consultas de lista, pañales y ficha ausente
  respondieron desde SQLite y «no compres» no creó órdenes. GPU RTX 3060: 3708/12288 MiB
  observados tras carga; modelo 1,7 GB, 100 % GPU en `ollama ps`. No Telegram, ajustes
  privados, compras ni habilitación del proveedor. Ver informe Task 3 del SDD.

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

## 2026-09-27 — Task 4: offers and browser contracts

- Added explicit store registry/protocol, equal-content quote ranking and exhaustive
  whole-line candidate assignments with grouped shipping quotes and incomplete coverage.
- Unknown shipping, conditional prices, incompatible references and implicit diaper
  pack rounding cannot become executable ranked offers. Formula still needs verification
  and a confirmed weight. Strengthened the previously masked formula-stage regression.
- Added headed Chromium with dedicated per-store profiles and cross-process exclusion,
  exact HTTPS navigation/resource policies, public DNS checks and guarded redirects.
  No real store adapter, login, credentials or purchase was used.
- RED: missing modules (3 collection errors), then explicit formula-range and browser
  redirect-chain regressions (2 failures). GREEN: 39 focused tests; full suite 147 passed.
- Playwright 1.63.0 / Chromium 153 installed and exercised locally. Cross-host and
  non-GET/HEAD redirects require intervention; manually fetched same-host redirects
   retain the original browser URL. Concrete adapters must inspect this limitation.

## 2026-09-27 — Task 5: durable checkout and reconciliation

- Added transactional line reservations, persistent store allocations, exclusive worker
  claims, pre-submit attempts, reconciliation and status/resume handling. Confirmations
  remove only the original revision, only after every allocation for that line confirms.
- Dry-run uses search/quote only and reports `simulado`; live checkout requires verified
  capabilities, exact contents, complete prices/delivery and extracted destination evidence.
- Added a focused persistence mixin behind the existing Repository API and schema v3.
  Runtime worker selectors and existing transactional outbox are exposed for task 7.
- RED: missing modules; subsequent regressions exposed price refresh, prepared-worker
  selection, stale product verification, legacy migration, notification duplication and
  mismatched durable allocation. GREEN: 27 focused tests, full suite 190 passed; Ruff clean.
- Used SQLite fault injection and fake external purchase ledgers only. No real purchases,
  credentials, stores or live capability claims. Runtime must enforce its OS process lock.

## 2026-09-28 — Task 6: public store observations (DONE_WITH_CONCERNS)

- Added four opt-in root `stores/` adapters, public discovery/product extraction and
  partial quote refreshes through the dedicated BrowserManager; no frozen live prices.
- Captured minimal anonymized real public fixtures September 27; repeated final public
  search/read/quote operations September 28, including Mercadona's strict 28023 region.
- Shipping/total/delivery unknown; no complete price comparison or minimum guarantee.
  GTIN independent evidence absent; formula reference remains disabled in the catalog.
- Prepare/submit/reconcile/live verification all disabled. Actual blockers include
  absent user sessions/destination, Amascotados unsolicited cart gift, Charro shipping
  discrepancy and unexplained Nappy add-to-cart failure. No purchases or account creation.
- Initial RED 15 failed/23 passed; safety regression RED 5 failed/41 passed and
  discovery RED 1 failed/46 passed. Final GREEN 47 store tests, 220 full-suite tests;
  Ruff clean. Detailed matrix: `docs/store-capabilities.md`.
- Controller confirmed flat layout; no migration. Old anonymous probe carts are ignored
  diagnostics, never reusable as prepared carts. Autonomous checkout remains blocked.

## 2026-09-28 — Task 8: integración offline y entrega (DONE_WITH_CONCERNS)

- Bot/TelegramIO, intérprete, SQLite, conversación, worker, tienda falsa, checkout y
  recuperación probados juntos: compra simulada tras reinicio, confirmación externa
  tras perder respuesta y reconciliación desconocida sin repetir submit.
- RED inicial del escenario diferido: 1 falló (`IndexError`, arnés de test hacía un
  ciclo menos y no procesaba el alta), 2 pasaron. GREEN: test integrado 3 passed;
  suite completa `251 passed`; `ruff check .`: All checks passed.
- `python -m shop_assistant doctor` devuelve 1: falta configuración privada; pide
  `configure` localmente. No se solicitaron credenciales aquí ni se creó tarea Windows.
  Telegram del usuario, arranque al iniciar sesión y pagos reales siguen sin comprobar.
  Las capacidades live de las cuatro tiendas permanecen inhabilitadas.
- Evidencia y bloqueos: `docs/superpowers/task-8-report.md`.

## 2026-09-29 — Gemma 4 local, Task 3: comprobación offline (PENDIENTE EN VIVO)

- `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader` informó
  `NVIDIA GeForce RTX 3060, 12288 MiB`; `Get-Command ollama` no encontró binario en
  `PATH`. Esto no demuestra que Ollama no esté instalado en otra ubicación.
- `gemma4:e2b` requiere una descarga aproximada de 7,2 GB más espacio para el servicio
  y descargas temporales; tampoco se ha medido el consumo adicional de contexto (4096)
  ni la VRAM/latencia durante inferencia.
- **Sin consentimiento para efectos externos:** no se instaló Ollama ni se descargaron
  pesos, no se activó `model-local`, no se accedió a configuración privada ni al bot
  Telegram vinculado, y no se probó ninguna compra. Conservar `commands_only`.
- **Pendiente con autorización expresa separada:** instalación y descarga; `ollama list`,
  respuesta local en español con `num_ctx=4096` y medición de tiempo/VRAM; luego, solo
  con sesión privada disponible, parar worker, activar e iniciar de nuevo y verificar
  frases seguras, reinicio, `/lista` y `/anadir` con Ollama detenido. No usar `/comprar`
  para esta prueba. La aceptación en Telegram y la aptitud real de GPU/modelo **no están
  demostradas** por tests con fakes.
- Parada/reversión futura: parar worker (`Ctrl+C` o `scripts/Stop-ShopAssistant.ps1`),
  `python -m shop_assistant model-local disable`, parar Ollama desde aplicación/servicio;
  opcionalmente `ollama rm gemma4:e2b` y desinstalar desde Aplicaciones instaladas.
  Consulta `docs/setup.md`. No se ha publicado ni subido esta rama.
- Verificación offline: `.venv\Scripts\python.exe -m pytest -q` excedió primero el
  límite de 120 s sin resultado final; repetido con límite de 600 s dio
  **285 passed in 120.78s**. `.venv\Scripts\python.exe -m ruff check .` dio
  **All checks passed!**; `git diff --check` sin errores y `git status --short`
  vacío tras los commits iniciales. Son tests con dobles, no pruebas del modelo real.
  Evidencia de GPU y de ausencia de `ollama` en `PATH` arriba; ninguna validación live.
- Documentación inicial en commits `bc7d1a4` y `4788bac`. El reporte detallado local
  `.superpowers/sdd/2026-09-29-gemma4-local-telegram/task-3-report.md` está ignorado
  por Git; esta sección conserva los resultados auditables en la rama.

## 2026-09-29 — Gemma 4 local, prueba voluntaria en este equipo (NO ACTIVADO)

- Tras autorización del usuario, se instaló Ollama 0.34.4 para el usuario actual mediante
  `winget install --id Ollama.Ollama --exact --scope user --silent`; winget comprobó la
  suma SHA-256 del instalador. El servicio escuchaba en `127.0.0.1:11434`.
- `ollama pull gemma4:e2b` terminó con `success` y `ollama list` mostró el modelo de
  7,2 GB. No se descargaron otras variantes ni se modificaron los perfiles de tiendas.
- Con el intérprete real del proyecto, `num_ctx=4096`, la primera frase «necesito arroz»
  agotó los 60 s de arranque en frío y devolvió aclaración. Con el modelo ya cargado,
  «necesito arroz» devolvió aclaraciones sobre el tipo/cantidad de arroz en cuatro
  intentos sucesivos (~0,6–0,9 s cada uno), no `add`. «No compres» devolvió `clarify`;
  «necesito Blemil etapa dos» también devolvió `clarify`. La salida del modelo varía.
- `ollama ps` indicó **100 % GPU** y contexto **4096**; `nvidia-smi` registró
  **3592 MiB** de VRAM total usada con el modelo cargado (antes: **755 MiB**).
  Esta medida es una instantánea, no un máximo durante inferencia.
- Una prueba exploratoria con instrucciones y ejemplo explícito de lista de compras
  produjo `add` para arroz, pero no forma parte del código entregado ni demuestra
  fiabilidad; se necesitarían pruebas reproducibles y una corrección revisada.
- **No se activó `model-local enable`, no se accedió a la configuración privada y no se
  enviaron mensajes al bot**: la prueba de aceptación en Telegram continúa pendiente.
  No se cambió el proveedor configurado previamente; las compras reales continúan
  deshabilitadas.
- Verificación posterior: `.venv\Scripts\python.exe -m pytest -q` → **299 passed
  in 139.89s**; `.venv\Scripts\python.exe -m ruff check .` → **All checks passed!**;
  `git diff --check` → sin errores. Son pruebas offline, no aceptación del modelo.
