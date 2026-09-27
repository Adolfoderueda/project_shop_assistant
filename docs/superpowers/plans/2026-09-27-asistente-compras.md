# Asistente de compras — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir un asistente local que reciba instrucciones por Telegram, conserve listas y órdenes y ejecute compras online respetando las referencias exactas del hogar.

**Architecture:** Un proceso Python asíncrono recibe mensajes mediante long polling, persiste entradas y trabajos en SQLite y coordina conexiones independientes con tiendas mediante Playwright. Un modelo interpreta mensajes en español mediante salida estructurada; las reglas de productos, estados y ejecución se comprueban en código. La comparación se limita inicialmente a tiendas conectadas y declara esa cobertura.

**Tech Stack:** Python 3.12 o superior, `python-telegram-bot`, SQLite de la biblioteca estándar, Pydantic 2, SDK de OpenAI con Responses API, Playwright con Chromium, pytest, pytest-asyncio, Ruff y Programador de tareas de Windows. Usar un entorno virtual y fijar las versiones efectivamente verificadas al implementar.

**Spec:** `docs/superpowers/specs/2026-09-27-asistente-compras-design.md`

## Global Constraints

- «Un único usuario podrá comunicarse por Telegram con un servicio alojado en su ordenador Windows».
- «La zona de entrega es 28023, Madrid». Dirección completa en configuración privada local.
- «Blemil tipo 1 Evolution, sin sustituciones de marca, gama ni etapa»; cotejar referencia antes de habilitarla.
- «Alpha Spirit Wild Fish / Only Fish, 12 kg», código `8436586310295`, sin sustituciones.
- «Exclusivamente Dodot talla 3». Libertad de gama y formato para la cantidad solicitada.
- «No se inventarán límites ni cantidades predeterminadas»; presupuesto y regularidad aplazados.
- «Un enlace identifica un producto; por sí solo no autoriza una compra».
- «No se afirmará que una tienda permite compra autónoma hasta haberlo verificado».
- «No repetir ciegamente la acción final de compra».
- Pruebas de compra real requieren una orden concreta con cantidades. No realizar pagos durante la implementación por inferir autorización del diseño.
- No crear suscripciones ni incrementar cantidades para obtener promociones sin instrucción.
- El repositorio está vacío salvo documentación y no tiene Git. Guardar hitos en `docs/superpowers/progress.md`; si se dispone de Git durante la ejecución, realizar commits por tarea, sin incluir secretos ni archivos ajenos.

## Review Focus

1. Mensaje recibido y apagado antes de procesarlo: no perder la orden por adelantar el offset de Telegram (tareas 1 y 3).
2. «No compres todavía», citas e instrucciones incrustadas en una ficha: no producir una orden ejecutable (tareas 2 y 4).
3. Cambio de formato, precio o contenido de carrito entre búsqueda y pago: no comprar un producto distinto ni líneas ajenas (tareas 4, 5 y 6).
4. Edición de lista mientras una compra está en curso: preservar la instantánea y no borrar nuevas necesidades (tarea 5).
5. Compra enviada y respuesta perdida: reconciliar antes de cualquier reintento, incluso después de reiniciar Windows (tareas 5 y 7).

## Decisiones de instalación y alcance

- No hay Python utilizable: `python --version` devuelve el aviso de instalación de Microsoft Store. Instalar CPython 3.12 o superior para el usuario actual al ejecutar el plan, verificar la versión y crear `.venv`; no modificar el alias del sistema como requisito.
- El bot es un proceso independiente, no una continuación automática de esta sesión. Necesita token propio de BotFather y, para conversación libre, credencial API de OpenAI. `OPENAI_MODEL` será un valor explícito cuya compatibilidad con salida estructurada se comprobará durante la configuración; no inferirlo del modelo del harness.
- Los comandos explícitos funcionarán sin modelo para diagnóstico. Sin credenciales, las pruebas usarán dobles locales y no se presentarán como bot conectado.
- Configuración privada en `%LOCALAPPDATA%\ShopAssistant`, con `settings.json`, `secrets.env`, `assistant.sqlite3`, `profiles/` y `logs/`. La documentación y `.env.example` contendrán solo ejemplos vacíos. Restringir acceso de archivos privados al usuario de Windows.
- Primera cobertura candidata: Mercadona para hogar; Charro desde Casa y Nappy para productos infantiles; Amascotados para pienso. Verificar el catálogo real antes de asignar productos a una tienda. No declarar un mínimo de todo Internet por comparar este conjunto. Una oferta externa podrá comunicarse como candidata, no usarse para compra hasta verificar la conexión.
- No abrir pagos reales como parte de la exploración. Una incompatibilidad de tienda se informa como bloqueo concreto y se revisa con el usuario; no se sustituye por una simulación presentada como solución final.

## Mapa de archivos

```text
pyproject.toml, requirements.lock, .gitignore, .env.example, README.md
src/shop_assistant/
  __init__.py, __main__.py, config.py, runtime.py, cli.py
  domain.py                     # Tipos comunes y estados
  storage.py, migrations/001.sql # Inbox, lista, pedidos, intentos y outbox
  catalog.py, restrictions.py    # Identidad y validación determinista
  conversation.py, interpreter.py# Acciones y lenguaje natural
  telegram_io.py                 # Polling duradero, autorización y avisos
  checkout.py, recovery.py       # Coordinación y reconciliación
  offers.py                     # Comparación de cotizaciones completas
  stores/
    base.py, registry.py, browser.py
    mercadona.py, amascotados.py, charro.py, nappy.py
tests/
  conftest.py, factories.py
  test_storage.py, test_conversation.py, test_telegram_io.py
  test_offers.py, test_checkout.py, test_recovery.py, test_runtime.py
  stores/test_contract.py, stores/test_browser.py
  stores/test_mercadona.py, stores/test_amascotados.py
  stores/test_charro.py, stores/test_nappy.py
  fixtures/stores/, fakes.py, test_end_to_end.py
scripts/install.ps1, scripts/start.ps1, scripts/register-task.ps1
scripts/unregister-task.ps1
docs/setup.md, docs/store-capabilities.md
```

Separar módulos de tienda por responsabilidad si su complejidad lo exige. Los fixtures de tiendas serán mínimos y anonimizados, sin cookies, direcciones ni información de pago.

## Tipos compartidos

En `domain.py`, usar modelos Pydantic estrictos con estos contratos; UUID como cadena para IDs, dinero en céntimos enteros y horas UTC:

- `IncomingMessage(update_id: int, user_id: int, chat_id: int, text: str)`.
- `ProductRule(id: str, brand: str, variant: str | None, stage: int | None, size: int | None, grams: int | None, gtin: str | None, verified: bool)`.
- `ListLine(id: str, product_id: str | None, description: str, quantity: int | None, revision: int)`.
- `Intent(action: Literal['add','remove','set_quantity','list','buy','status','resume','clarify'], lines: list[IntentLine], order_id: str | None, question: str | None)`, `IntentLine(line_id: str | None, description: str | None, quantity: int | None, url: str | None)`.
- `Reply(text: str, order_id: str | None)`; `Order(id: str, lines: list[ListLine], mode: Literal['dry_run','live'])`.
- `Offer(store_id: str, product_id: str, url: str, title: str, gtin: str | None, brand: str, variant: str | None, stage: int | None, size: int | None, grams: int | None, units_per_pack: int, price_cents: int, in_stock: bool, conditions: list[str], observed_at: datetime)`.
- `Destination(postcode: str, address: str)`; dirección no enviada al intérprete.
- `Quote(store_id: str, items: list[QuotedLine], shipping_cents: int | None, total_cents: int | None, currency: Literal['EUR'], delivery: str | None, observed_at: datetime)`, `QuotedLine(line_id: str, offer: Offer, packs: int)`.
- `Capabilities(search: bool, quote: bool, prepare: bool, submit: bool, reconcile: bool, live_verified: bool)`.
- `PreparedCart(id: str, quote: Quote, fingerprint: str)`; huella basada en identidad, cantidad y total, no en texto libre.
- `Submission(status: Literal['confirmed','requires_intervention','uncertain','failed'], external_id: str | None, total_cents: int | None, delivery: str | None, reason: str | None)`.
- `Reconciliation(status: Literal['confirmed','definitely_not_submitted','unknown'], submission: Submission | None)`; una lista vacía de pedidos no basta para `definitely_not_submitted`.

Las cantidades positivas representan envases o unidades de compra especificadas. Una petición de pañales por número de piezas debe aclarar el redondeo a paquetes si no es exacto; no decidirlo silenciosamente. Fórmula y pienso se comparan en formatos confirmados. Registrar estados de subpedido del diseño y un resultado separado `simulado` para dry-run.

### Tarea 1: Persistencia y catálogo duraderos

**Files:** crear configuración de proyecto, `config.py`, `domain.py`, `storage.py`, `migrations/001.sql`, `catalog.py`, `restrictions.py`, `tests/factories.py`, `tests/test_storage.py`.

**Interfaces:** `Repository(path: Path).migrate() -> None`; `ingest_batch(messages: list[IncomingMessage], next_offset: int) -> None`; `pending_messages() -> list[IncomingMessage]`; `apply_intent(update_id: int, intent: Intent, mode: str) -> Reply`; `list_lines() -> list[ListLine]`; `get_order(order_id: str) -> Order`; `telegram_offset() -> int`. `validate_product(rule: ProductRule, offer: Offer) -> list[str]` devuelve razones de rechazo.

- [ ] Instalar/verificar Python y crear el entorno virtual; añadir dependencias y configuración de pytest/Ruff en `pyproject.toml`, ignorar `.venv`, cachés, datos privados y artefactos de navegador.
- [ ] Escribir pruebas `test_batch_and_offset_are_atomic`, `test_order_survives_reopen`, `test_duplicate_update_creates_one_order` y `test_restrictions_reject_near_matches`. Aserciones: tras rollback `telegram_offset() == old_offset`; tras reapertura `get_order(id).lines == snapshot`; una repetición devuelve el mismo `order_id`; pienso GTIN distinto, Dodot talla 4 y Blemil etapa 2 producen razones de rechazo.
- [ ] Ejecutar `.venv\Scripts\python.exe -m pytest tests/test_storage.py -q`; confirmar fallos por API ausente.
- [ ] Implementar migración y operaciones transaccionales: inbox única por `update_id`, meta offset, lista versionada, órdenes y líneas inmutables, subpedidos, intentos y outbox. Completar inbox, aplicar intención y generar aviso en la misma transacción. Usar claves foráneas, `busy_timeout`, WAL y transacciones cortas sin llamadas de red.
- [ ] Sembrar reglas: pienso confirmado con 12000 g y GTIN indicado; pañales Dodot talla 3; fórmula Blemil 1 Evolution pendiente de cotejo, sin completar GTIN ni formato inventados. Validar cantidades `> 0` si están presentes.
- [ ] Ejecutar las pruebas anteriores hasta PASS; registrar el hito y fijar versiones resueltas en `requirements.lock`.

### Tarea 2: Conversación y órdenes explícitas

**Files:** `conversation.py`, `interpreter.py`, `tests/test_conversation.py`, `tests/fakes.py`.

**Interfaces:** `Interpreter.parse(text: str, lines: list[ListLine]) -> Intent` asíncrono; `Conversation(repo: Repository, interpreter: Interpreter).handle(message: IncomingMessage, mode: str) -> Reply` asíncrono. Consume `apply_intent` de tarea 1. Implementar `OpenAIInterpreter(client: AsyncOpenAI, model: str)` y parser de comandos.

- [ ] Escribir pruebas `test_add_does_not_buy`, `test_negated_purchase_is_not_order`, `test_unresolved_quantity_requests_clarification`, `test_ambiguous_remove_changes_nothing`, `test_llm_refusal_changes_nothing`. Usar entradas «añade pañales», «no compres todavía», «compra lo pendiente» con cantidad ausente, dos líneas similares y salida del modelo nula; afirmar cero órdenes ejecutables o cero mutaciones según corresponda.
- [ ] Ejecutar `.venv\Scripts\python.exe -m pytest tests/test_conversation.py -q` y confirmar fallos esperados.
- [ ] Implementar salida estructurada con `AsyncOpenAI.responses.parse(..., text_format=Intent)`, timeout y tratamiento de error/nulo. El modelo no obtiene herramientas de pago. Contexto restringido a texto del usuario y lista; URL es referencia, no instrucción. Revalidar IDs, cantidades y acción en código. Guardar aclaraciones pendientes por usuario para interpretar la respuesta siguiente.
- [ ] Añadir comandos `/lista`, `/anadir <texto>`, `/quitar <id>`, `/cantidad <id> <n>`, `/comprar`, `/estado <id>` y `/continuar <id>` como ruta determinista. No ejecutar compras por respuestas del bot, citas ni resultados de búsqueda. Incluir ejemplos adversariales en la prueba del intérprete; cualquier salida ambigua solicita aclaración.
- [ ] Ejecutar pruebas hasta PASS y registrar hito.

### Tarea 3: Telegram autorizado con recepción duradera

**Files:** `telegram_io.py`, `tests/test_telegram_io.py`.

**Interfaces:** `TelegramIO(bot: telegram.Bot, repo: Repository, allowed_user_id: int).poll_once() -> None`, `.send_pending() -> None`, métodos asíncronos; consume `IncomingMessage` y las operaciones de inbox/outbox de tarea 1. Añadir `Repository.pending_notices() -> list[tuple[str,int,str]]` y `mark_notice_sent(id: str) -> None`.

- [ ] Escribir `test_unauthorized_and_group_messages_ignored`, `test_crash_before_dispatch_preserves_input`, `test_offset_never_acknowledges_uncommitted_batch`, `test_failed_notification_is_retried`. Verificar usuario exacto y chat privado, persistencia antes de siguiente `get_updates(offset=...)`, y aviso pendiente tras timeout.
- [ ] Ejecutar `.venv\Scripts\python.exe -m pytest tests/test_telegram_io.py -q`; confirmar RED.
- [ ] Usar `telegram.Bot.get_updates` directamente para controlar el offset: persistir lote y siguiente offset en una transacción antes de solicitar otro lote; procesar inbox independientemente. No usar el updater automático que adelanta recepción en memoria. Solicitar solo mensajes, no descartar pendientes al arrancar. Entradas no autorizadas se ignoran sin guardar su texto y sin bloquear el avance del offset.
- [ ] Implementar outbox con reintento acotado y espera ante `RetryAfter`. Registrar IDs de avisos; avisar que Telegram no ofrece envío exactamente una vez si se pierde la respuesta, sin permitir que un aviso duplicado duplique una compra. Enviar texto plano para evitar interpretar Markdown de productos.
- [ ] Ejecutar pruebas hasta PASS; registrar hito. No pedir al usuario que publique tokens en la conversación: instalación local en tarea 7.

### Tarea 4: Ofertas, contratos de tienda y navegador local

**Files:** `offers.py`, `stores/base.py`, `stores/registry.py`, `stores/browser.py`, `tests/test_offers.py`, `tests/stores/test_browser.py`, `tests/stores/test_contract.py`.

**Interfaces:** protocolo `StoreAdapter`: `capabilities() -> Capabilities`; async `search(rule: ProductRule) -> list[Offer]`, `quote(items: list[QuotedLine], destination: Destination) -> Quote`, `prepare(quote: Quote) -> PreparedCart`, `submit(cart: PreparedCart, attempt_id: str) -> Submission`, `reconcile(attempt_id: str, cart: PreparedCart) -> Reconciliation`. `rank_quotes(quotes: list[Quote]) -> list[Quote]`. `BrowserManager.open(store_id: str) -> BrowserContext` async y `close() -> None` async.

- [ ] Escribir pruebas `test_shipping_changes_cheapest`, `test_unknown_shipping_is_not_ranked_as_free`, `test_conditional_discount_is_not_universal`, `test_unverified_formula_is_rejected`, `test_untrusted_page_cannot_change_rules`, `test_profile_is_exclusive`. Ejemplo: total 2500+600 pierde frente a 2800+0; envío nulo no recibe rango de oferta completa; dirección/credenciales no llegan al intérprete.
- [ ] Ejecutar `.venv\Scripts\python.exe -m pytest tests/test_offers.py tests/stores/test_contract.py tests/stores/test_browser.py -q`; confirmar RED.
- [ ] Implementar comparación por total de cesta para cantidades iguales, y precio por unidad informativo para pañales. Considerar todas las asignaciones viables entre las pocas tiendas conectadas para incorporar umbrales de envío; si no hay cotización verificable, excluir esa combinación e informar cobertura incompleta. No usar precios vistos en esta conversación como datos vigentes.
- [ ] Implementar contextos persistentes Playwright separados por tienda, Chromium visible, perfil dedicado y exclusión mutua; solo dominios HTTPS permitidos por registro. Validar enlaces/redirecciones; rechazar localhost, IP privadas y dominios ajenos. No ejecutar código ni órdenes extraídas de una página.
- [ ] Ejecutar pruebas hasta PASS y registrar hito.

### Tarea 5: Ejecución, reconciliación e idempotencia

**Files:** `checkout.py`, `recovery.py`, `tests/test_checkout.py`, `tests/test_recovery.py`, ampliar `storage.py` y `tests/fakes.py`.

**Interfaces:** `CheckoutService(repo: Repository, stores: dict[str, StoreAdapter], destination: Destination).run(order_id: str) -> None` async; `Recovery(repo: Repository, stores: dict[str, StoreAdapter]).recover() -> None` async. Añadir repositorio `claim_order(order_id: str) -> bool`, `save_attempt(order_id: str, store_id: str, cart: PreparedCart) -> str`, `record_submission(attempt_id: str, result: Submission) -> None`, `uncertain_attempts() -> list[tuple[str,PreparedCart]]`. Claims exclusivos dentro del proceso protegido y persistencia del estado antes de acciones externas.

- [ ] Escribir `test_dry_run_never_calls_submit`, `test_lost_response_reconciles_without_resubmit`, `test_partial_success_preserves_remaining_lines`, `test_edit_during_checkout_preserves_new_revision`, `test_second_purchase_does_not_claim_already_pending_lines`, `test_cart_fingerprint_change_requotes`. Afirmar `submit_calls == 0` en dry-run, `submit_calls == 1` tras recuperación incierta, y que nuevas revisiones sobreviven al confirmar la instantánea antigua.
- [ ] Ejecutar `.venv\Scripts\python.exe -m pytest tests/test_checkout.py tests/test_recovery.py -q`; confirmar RED.
- [ ] Implementar snapshot, reserva de líneas y cotización. Antes de submit, revisar identidad, cantidades, líneas ajenas, destino, entrega y total. Un cambio de precio solicita nueva cotización y comunica el cambio; no añade un umbral de presupuesto ni un circuito de aprobación financiera no acordado. Datos de entrega indispensables faltantes generan intervención.
- [ ] Guardar estado `enviando` e intento antes de tocar el botón final. `confirmed` requiere evidencia externa. Timeout después de submit genera `resultado_incierto`; `unknown` no habilita reintento automático. En reanudación tras verificación bancaria, reconciliar primero.
- [ ] Marcar dry-run como `simulado`, sin retirar líneas como compradas. Evitar mutar el carrito remoto en dry-run: preparación simulada o lectura, sin acción final; prueba controlada de preparación real se distingue explícitamente y revisa líneas preexistentes.
- [ ] Ejecutar pruebas hasta PASS y registrar hito.

### Tarea 6: Conexiones reales y matriz de capacidades

**Files:** los cuatro módulos `stores/mercadona.py`, `stores/amascotados.py`, `stores/charro.py`, `stores/nappy.py`; sus cuatro pruebas; `tests/fixtures/stores/`; `docs/store-capabilities.md`.

**Interfaces:** cada clase implementa `StoreAdapter` de tarea 4 sin modificar su contrato. Registro por IDs `mercadona`, `amascotados`, `charro`, `nappy`. Datos encontrados en páginas no alteran el catálogo de restricciones.

- [ ] Inspeccionar con navegador el flujo público de cada candidato: producto, catálogo, códigos identificadores, gastos de envío, carrito, acceso, pago e historial accesible. Comenzar por la URL confirmada del pienso y código postal 28023 para Mercadona. Registrar fecha y evidencia anonimizada de cada capacidad. No inventar selectores ni endpoints privados.
- [ ] Si se necesita acceso, abrir el perfil dedicado y solicitar al usuario iniciar sesión localmente. Clasificar capacidades como `no_comprobada`, `probada_sin_pago`, `probada_con_pedido_real` o `bloqueada`, con motivo concreto. El modelo de `Capabilities` solo habilita operaciones implementadas; `live_verified` permanece falso hasta evidencia real.
- [ ] Para cada tienda viable, capturar fixtures públicos mínimos y escribir `test_exact_product_extraction`, `test_out_of_stock`, `test_existing_foreign_cart_requires_intervention`, `test_checkout_requires_bank_action` y `test_success_requires_order_reference`. Afirmar GTIN/formato y céntimos extraídos de su fixture, cero submit si hay líneas ajenas, y estado incierto si solo desaparece el botón sin referencia de pedido.
- [ ] Ejecutar `.venv\Scripts\python.exe -m pytest tests/stores -q`; confirmar fallos de los adaptadores todavía ausentes.
- [ ] Implementar búsqueda/cotización con datos reales y selectores observados por tienda; añadir revisión del carrito, submit y reconciliación donde el flujo inspeccionado lo permita. Reusar transporte/navegador, no suponer que tiendas con aspecto similar comparten checkout. CAPTCHA, sesión caducada y 3DS devuelven intervención, sin bucles de evasión.
- [ ] Probar adaptadores contra fixtures y recorrido real de solo lectura. Registrar por separado funciones verificadas y pasos que faltan. Si no puede implementarse una tienda, detener esa integración y presentar el bloqueo para elegir otra; completar el resto del flujo sin afirmar que la tarea global está terminada.
- [ ] Ejecutar suite `tests/stores` hasta PASS para implementaciones disponibles y registrar hito y bloqueos. Las pruebas de fixtures no cuentan como compra real verificada.

### Tarea 7: Instalación, configuración y funcionamiento continuo

**Files:** `__main__.py`, `cli.py`, `runtime.py`, cuatro scripts PowerShell del mapa, `docs/setup.md`, `README.md`, `tests/test_runtime.py`.

**Interfaces:** `load_settings(root: Path) -> Settings` en `config.py`; `run(settings: Settings) -> None` async en `runtime.py`; CLI `python -m shop_assistant {configure,doctor,run,login,verify-product}`. `Settings` incluye token, allowed_user_id, modelo/clave opcionales, destino, ruta de datos y modo explícito. `login --store <id>` abre el perfil dedicado; `verify-product --id formula` exige referencia proporcionada/cotejada antes de marcarla verificada.

- [ ] Escribir `test_missing_configuration_has_actionable_message`, `test_second_process_cannot_start`, `test_restart_recovers_before_new_checkout`, `test_shutdown_preserves_pending_work`, `test_logs_redact_secrets`. Verificar que el segundo proceso sale sin procesar pedidos y la recuperación precede a nuevas compras.
- [ ] Ejecutar `.venv\Scripts\python.exe -m pytest tests/test_runtime.py -q`; confirmar RED.
- [ ] Implementar configuración local interactiva: token BotFather oculto, identificación del usuario mediante nonce generado en consola y `/start <nonce>` en chat privado, configuración del modelo y destino. Antes de completar vinculación no atender órdenes. Verificar token/API mediante llamadas de diagnóstico y no escribir secretos en logs.
- [ ] Implementar exclusión global por mutex de Windows, ciclo asíncrono para polling, inbox, pedidos y outbox, parada ordenada y recuperación al inicio. Añadir rotación de logs sin cuerpos sensibles y `doctor` que compruebe configuración, SQLite, conectividad, navegador y capacidades sin comprar.
- [ ] Crear instalación reproducible, script de arranque con rutas absolutas entrecomilladas y tarea programada al iniciar sesión del usuario. Usar token interactivo para navegador visible, reiniciar ante fallo y no finalizar por duración. Documentar que no arranca antes del inicio de sesión; no activar autologin ni modificar suspensión sin decisión del usuario.
- [ ] Ejecutar pruebas hasta PASS; verificar `doctor`, arranque/parada, perfiles y persistencia. Registrar instalación de la tarea solo cuando configuración y pruebas locales estén listas.

### Tarea 8: Verificación integrada y entrega

**Files:** `tests/test_end_to_end.py`, ampliar `tests/fakes.py`, `README.md`, `docs/setup.md`, `docs/store-capabilities.md`, `docs/superpowers/progress.md`.

**Interfaces:** consumir componentes anteriores sin introducir otra arquitectura. Fakes de Telegram, intérprete y tiendas implementan exactamente sus contratos; ninguna prueba automática necesita credenciales reales ni paga.

- [ ] Escribir `test_telegram_to_simulated_receipt_after_restart`: mensaje añade pienso exacto, cantidad explícita, compra, reinicio, recuperación y notificación simulada; afirmar `submit_calls == 0` y conservación de la lista. Añadir `test_confirmed_order_is_not_repeated_after_crash` con tienda falsa que conserva pedido externo y confirma un único submit tras reconciliar.
- [ ] Ejecutar `.venv\Scripts\python.exe -m pytest tests/test_end_to_end.py -q`; corregir exclusivamente integración necesaria hasta PASS.
- [ ] Ejecutar `.venv\Scripts\python.exe -m pytest -q` y `.venv\Scripts\python.exe -m ruff check .`; exigir PASS y cero errores. Guardar evidencia de comandos en progreso.
- [ ] Con configuración del usuario, comprobar desde su Telegram añadir/listar/modificar, pedir prueba, reiniciar servicio, consultar estado y recibir aviso. Probar inicio de sesión de Windows con su colaboración; si no puede verificarse ahora, indicarlo como pendiente y no afirmar disponibilidad 24/7 comprobada.
- [ ] Solicitar cotejo de fórmula si sigue pendiente, mediante foto/enlace localmente configurado; esto bloquea solo compras de fórmula. Documentar capacidades por tienda y cómo resolver intervención bancaria en el navegador.
- [ ] Entregar comandos de uso, arranque, parada y desinstalación de la tarea. Si el usuario pide una compra real concreta, verificar esa orden y registrar evidencia sin capturar datos de pago. Si no la pide, informar que el pago real sigue sin comprobar, sin convertirlo en una compra de prueba no solicitada.
- [ ] Realizar revisión final de requisitos, fallos de compra duplicada, datos privados y capacidades declaradas; corregir hallazgos y repetir únicamente comprobaciones afectadas. Actualizar estado final con partes funcionales y bloqueos concretos.

## Fuentes técnicas consultadas

- python-telegram-bot: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-requested-design-patterns — integración asíncrona; se elige polling propio mediante Bot para conservar offset duradero.
- Playwright Python: https://playwright.dev/python/docs/api/class-browsertype — `launch_persistent_context`, exclusividad y perfil dedicado.
- OpenAI Python: https://github.com/openai/openai-python/blob/main/helpers.md — `responses.parse`, Pydantic y manejo de `output_parsed` ausente.

## Revisión del plan

Cobertura: objetivo y alcance en tareas 2/8; arquitectura/datos en 1/4/5/7; restricciones en 1/4/6; conversación en 2/3; estados y recuperación en 5/7; configuración privada en 7; tiendas en 4/6; aceptación en pruebas de todas las tareas y 8. Los cinco riesgos de Review Focus tienen pruebas asignadas. Las capacidades de checkout se basarán en inspección real y no en suposiciones sobre las páginas.

## Handoff

Pendiente de revisión del usuario y elección del método de ejecución. Recomendación: ejecución en esta sesión, porque las tareas comparten contratos y la inspección de tiendas necesita continuidad con la configuración local. Alternativa: agentes por tarea con revisión independiente entre tareas, de mayor coste de contexto. No comenzar implementación antes de esa elección y aprobación del plan.
