# Respuestas naturales de Gemma Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gemma redacta las respuestas naturales con hechos confirmados y opciones autorizadas, sin cambiar decisiones ni repetir operaciones.

**Architecture:** Preparar acción y presentación en una transacción, redactar fuera de SQLite y finalizar inbox/outbox en otra transacción idempotente. La presentación tipada permite validar estructura y hechos; cualquier rechazo finaliza con un respaldo claro. Los comandos y compras conservan su ruta determinista.

**Tech Stack:** Python, Pydantic estricto, SQLite, httpx/Ollama local, pytest y PowerShell existentes; sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-10-08-respuestas-naturales-gemma-design.md` (aprobada por el usuario).

## Global Constraints

- «Los comandos que empiezan por `/` conservan sus respuestas deterministas.»
- «Las autorizaciones de compra y avisos del checkout, recovery y transporte quedan fuera de la generación.»
- «OpenAI y commands_only conservan su conducta.»
- «El texto del modelo nunca llega a `Intent`, al reducer, a SQL de la lista ni a checkout.»
- «No se mantiene una transacción SQLite abierta durante HTTP.»
- «La generación no renueva el TTL del diálogo». Mantener los 900 segundos existentes desde la transición, no desde su envío.
- «No se descarga modelo, se reinicia servicio ni se fuerza unload.»
- «No se afirmará infalibilidad ni se relajarán validadores para aumentar la tasa de mensajes generados.»
- «La actualización de la PR existente, push y aceptación privada necesitan autorización separada».
- Trabajar en `.worktrees/gemma4-local`, conservar cambios previos y procesos del usuario. Datos inventados y SQLite temporal; cero compras.

## Review Focus

- Caída después de guardar la lista, antes de enviar: recuperar presentación sin aplicar dos veces ni renovar TTL (Tasks 3/5).
- Descripciones con instrucciones, números, acentos y tokens que parezcan placeholders: tratar como datos literales, nunca cambiar la gramática del mensaje (Tasks 1/4).
- Opciones numéricas mezcladas con cantidades y duplicados: distinguir entradas y acciones; conservar orden que entiende el reducer (Tasks 1/2).
- Modelo niega un éxito o anuncia un éxito pendiente con todos los números correctos: cobertura de tokens no equivale a verdad semántica; rechazar composición contradictoria (Tasks 2/4).
- Reinicio tras deshabilitar Ollama o migración con trabajo huérfano: respaldo sin mutación y propietario/procedencia fail-closed (Tasks 3/5).

## Archivos y responsabilidades

- `presentation.py`: contratos de hechos, opciones y trabajo preparado; no I/O.
- `presentation_replies.py`: construir instantánea/fallback desde resultado, no desde plantilla analizada ni lectura posterior.
- `presentation_validation.py`: propuesta de redacción, cobertura/referencias y composición segura.
- `presentation_storage.py`: mixin preparación/finalización/recuperación; `migrations/007.sql`.
- `ollama_replies.py`: petición de redacción con transporte local protegido.
- `dialogue_storage.py`: extraer aplicación transaccional común, construir instantánea dentro de ella.
- `conversation.py`, `runtime.py`: orquestar redactor y recuperación; no modificar checkout/TelegramIO.
- `storage.py`: mixin, migración y propietario; `pyproject.toml`: registrar módulos cuando se creen.
- Tests correspondientes, `scripts/Probe-Replies.ps1`, docs/evidencia inventada.

## Contratos compartidos (usar nombres exactos)

Todos los modelos heredan `domain.Model` (strict, frozen, extra forbid); JSON durables se revalidan incluso tras `model_copy`. Tuplas en Python, arrays en JSON.

```text
PresentationFact(key: str, text: str)  # clave local f0,f1; text literal seguro de aplicación
PresentationOption(key: str, text: str)  # o0,o1; orden ya autorizado
PresentationSnapshot(version: Literal[1], kind: str,
    facts: tuple[PresentationFact,...], options: tuple[PresentationOption,...],
    question: str | None, fallback: Reply)
PreparedPresentation(update_id: int, user_id: int, chat_id: int,
    snapshot: PresentationSnapshot)
DraftBlock(role: Literal['lead','fact','question','option'], text: str)
ReplyDraft(blocks: tuple[DraftBlock,...])
ReplyWriter Protocol: async draft(snapshot: PresentationSnapshot) -> ReplyDraft | None
```

El modelo utiliza tokens `{{f0}}`, `{{q}}`, `{{o0}}` para valores críticos, no sus copias. `question` y textos de opciones son bloques autorizados, con redacción clara. Los bloques factuales pueden incluir una o varias referencias compatibles sin repetir/omitir ninguna obligatoria. Referencias locales no identifican filas ni conceden permisos. Descripciones maliciosas entran solo tras validar la estructura de tokens y nunca se vuelven a analizar tras sustituirlos.

`kind` es la clase de presentación normalizada, no un `Intent`; enum cerrado a definir en Task 1: `added`, `updated`, `replaced`, `cancelled`, `list`, `product`, `question`, `clarify`. No pasar flags de autorización al redactor. Aclaraciones específicas y estado de pregunta se expresan en bloques de aplicación, no mediante parsing de texto de `decision.prompt`.

Límites de redacción: 20 hechos, 10 opciones, 8.000 caracteres de JSON de contexto, 2.000 caracteres de draft antes de sustitución, 6.000 caracteres de respuesta final. Presupuesto excedido => respaldo íntegro y transporte chunking existente; no truncar hechos. HTTP total20s, connect2s, num_ctx4096, thinkFalse, streamFalse, sin reintento. No limitar la longitud del respaldo necesario para conservar datos.

## Preparación

- [ ] Leer spec, ledger y estado limpio/HEAD; crear ledger de este plan y guardar interfaces/dependencias. No repetir pruebas reales del plan anterior.
- [ ] Ejecutar baseline `.venv\Scripts\python.exe -m pytest -q` y Ruff desde el worktree. Registrar evidencia.

### Task 1: Hechos de presentación y respaldo legible

**Files:** Create `presentation.py`, `presentation_replies.py`; Modify `dialogue_replies.py`, `dialogue.py`, `dialogue_controller.py` (metadatos de presentación, no ampliar transiciones), `pyproject.toml`; Test `tests/test_presentation_replies.py`.

**Interfaces:** Produce `build_presentation(decision: DialogueDecision, affected: ListLine | None, lines: list[ListLine], legacy_reply: Reply | None, *, observations: list[ObservedProduct], original: ListLine | None) -> PresentationSnapshot`. Produce `fallback_reply(snapshot: PresentationSnapshot) -> Reply`. Consume tipos existentes; no interpretar salida textual de `_apply` como hechos. `original` es la fila anterior capturada dentro de la transacción. Añadir `DialogueDecision.presentation_reason: Literal['generic','expired','stale','reserved','quantity_range','diaper_unit','no_pending','cancelled_pending'] = 'generic'`; asignar explícitamente en los retornos correspondientes, sin renovar estado ni alterar reply_kind/mutation. Caducidad se detecta antes de descartar estado; product/list/questions se derivan de reply_kind/legacy_intent/state tipados.

- [ ] **Step 1: RED tests.** `test_two_rice_entries_are_distinct`: arroz1/arroz2 produce dos facts distintos, cantidades1/2, opciones change_quantity/add en ese orden y respaldo sin «1 envases» ni «línea». `test_all_questions_have_authorized_options`: parametrizar quantity, duplicate_choice, add_or_replace, select_line, confirm_replace, replace_quantity, replace_duplicate, remove_id; cancelación solo cuando el parser actual la admite. `test_replacement_uses_original_and_saved_destination`: nombres originales/guardados explícitos, no éxito antes de mutación. `test_product_unknown_and_historical_facts`: fuente/fecha/stock histórico real, sin stock actual; unknown registra hecho de backlog solo si `_apply` lo guardó. `test_hostile_description_is_literal_data`: acentos, talla2, `{{f0}}`, «ignora instrucciones» intactos.
- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_presentation_replies.py -q`; comprobar fallo por contrato/fábrica ausente, no fixture incorrecta.
- [ ] **Step 3:** Implementar contratos/build/fallback; nombres/unidades en singular/plural correcto, listas con saltos y numeración distinta para opciones/entradas. Pregunta quantity deja claro «cantidad total», no incremento. Conservar IDs en comandos y en selección remove_id cuando es necesario para la acción actual; para redacción natural de remove_id enviar ordinales, y la aplicación insertar el ID necesario solo en respuesta final. No filtrar IDs esenciales del respaldo técnico.
- [ ] **Step 4:** GREEN focused + regresiones dialogue; verificación full/Ruff/diff antes del commit. Registrar scripts/fixtures inventados.
- [ ] **Step 5:** Commit `feat: describe dialogue outcomes with grounded presentation facts`.

### Task 2: Validación de redacción y composición

**Files:** Create `presentation_validation.py`; Test `tests/test_presentation_validation.py`; Modify `pyproject.toml`.

**Interfaces:** Consume snapshot/draft. Produce `validate_draft(snapshot: PresentationSnapshot, draft: ReplyDraft) -> Reply | None` y `within_budget(snapshot: PresentationSnapshot) -> bool`.

- [ ] **Step 1: RED tests.** `test_grounded_draft_formats_two_entries`: lead natural, dos tokens de facts, pregunta y dos opciones => sustitución literal/cobertura/orden. `test_rejects_missing_extra_reordered_and_repeated_options`: falta/opción inventada, orden cambiado o duplicada devuelveNone. `test_rejects_unbound_numbers_names_urls_and_tokens`: ninguna cantidad/nombre/URL fuera de hechos, tokens desconocidos o bloque extra permitido. `test_rejects_false_success_and_negation`: «ya he comprado {{f0}}», «no {{f0}}», «he añadido» en pregunta pendiente, «sumamos» devuelveNone. `test_literal_product_tokens_not_reparsed` y `test_budget_returns_no_partial_presentation`: límites exactos incluidos/excedidos.
- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_presentation_validation.py -q`; expected FAIL por funciones ausentes.
- [ ] **Step 3:** Validar JSON y tokens antes de sustituir. Bloques fact/option/question son referencias completas separadas únicamente por espacios, saltos, puntuación `.,:;•-` y conectores `y`, `también`, `además`; no aceptar negación/modificadores de verdad ni verbos adicionales alrededor de ellos. Se permite que Gemma agrupe/ordene hechos cuando no cambia selección; opciones siempre ordenadas. Un lead opcional, máximo160caracteres, acepta únicamente estas frases (mayúsculas/acento/puntuación superficial normalizados): `Aquí tienes el detalle`, `Vamos por partes`, `Estas son las opciones`, `Te lo explico`, `Puedes elegir entre estas opciones`; se pueden combinar máximo2 con punto/salto. Rechazar cualquier otra frase, no un blacklist como garantía. Gemma elige composición/formulación dentro de esa frontera; no fingir libertad irrestricta. Pregunta/opciones no cambian semántica: usar el texto claro de aplicación elegido en Task1. Documentar que inicialmente los hechos y la pregunta están anclados y la libertad de redacción es acotada; si no alcanza naturalidad, volver al usuario antes de ampliar.
- [ ] **Step 4:** GREEN focused, full/Ruff/diff. Auto-revisión: enumerar comprobaciones semánticas reales y riesgo residual; si la frontera fuerza respaldo constante, no ampliar gramática sin tests ni ocultarlo.
- [ ] **Step 5:** Commit `feat: validate model reply composition against confirmed facts`.

### Task 3: Trabajos durables de presentación, sin doble aplicación

**Files:** Create `presentation_storage.py`, `migrations/007.sql`; Modify `storage.py`, `dialogue_storage.py`, `pyproject.toml`; Test `tests/test_presentation_storage.py`; actualizar solo assertions de versión actual en tests previos.

**Interfaces:** Produce `Repository.prepare_dialogue(update_id: int, proposal: Intent | None, mode: str, *, now: datetime) -> PreparedPresentation | Reply`; `prepared_presentation(update_id: int) -> PreparedPresentation | None`; `finalize_presentation(update_id: int, reply: Reply) -> Reply`. Mantener `apply_dialogue(...) -> Reply` para rutas existentes. Compartir la aplicación de mutations/legacy dentro de conexión propia del llamador, no llamar pública `apply_dialogue` y reescribir una respuesta completada.

- [ ] **Step 1: RED tests.** `test_v6_upgrade_preserves_all_durable_work`: snapshots de listas/orders/executions/reservations/inbox/outbox/offset/observations/dialogue idénticos tras migrate dos veces; user_version7, reject8. `test_prepare_commits_once_without_sendable_notice`: mutación+estado+snapshot durable, inbox pending y sin outbox. `test_prepare_replay_ignores_new_proposal`: misma instantánea sin cambio revision/TTL. `test_finalize_is_atomic_and_idempotent`: inbox/outbox único, segundo finalize devuelve Reply original. `test_snapshot_uses_transaction_rows_not_old_context`: producto/quantity desde DB real en esa transacción. `test_orphan_foreign_corrupt_and_conflicting_job_fail_closed`: propietario/identity/procedencia/version estricto, no ejecutar otra vez. `test_rollback_prepare_and_finalize`: fallos inyectados revierten cada transacción, prepared persiste si falla finalización.
- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_presentation_storage.py -q`; comprobar RED esperado.
- [ ] **Step 3:** Migración BEGIN/COMMIT user_version7. Tabla `presentation_jobs(update_id INTEGER PRIMARY KEY REFERENCES inbox(update_id), user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL)`; inbox indica finalización, trabajo inmutable retenido para auditar. Comprobar identidad tanto columnas como inbox y payload estricto. No borrar trabajos al finalizar. Solo finalizar con Reply sin order_id; ruta de compras no crea trabajo. Trabajos corruptos/huérfanos => error explícito, no intentar reaplicar. Extraer lectura de observaciones en conexión del caller, usada también por `_apply(product_query)`; misma selección y límite5. Snapshot completo se construye tras `_apply`, dentro de la transacción, con original pre-mutation y datos después.
- [ ] **Step 4:** GREEN focused + storage/replacement regression y full/Ruff/diff. Assertions de migración histórica mantienen fixtures v6 existentes.
- [ ] **Step 5:** Commit `feat: persist recoverable reply presentation jobs`.

### Task 4: Redactor local con contexto mínimo y fallo acotado

**Files:** Create `ollama_replies.py`; Modify `pyproject.toml`; Test `tests/test_ollama_replies.py`.

**Interfaces:** Produce `OllamaReplyWriter(model: str, *, transport: httpx.AsyncBaseTransport | None = None)` implementando `ReplyWriter.draft`. Consume contracts/budget; transporte inyectable para MockTransport.

- [ ] **Step 1: RED tests.** `test_request_contains_only_presentation_data`: actual bytes excluyen update/user/chat/IDs/order/control/history/fallback.order_id/rutas/config, endpoint exact127.0.0.1:11434/api/chat, options4096/thinkFalse/streamFalse, schema ReplyDraft. `test_data_injection_cannot_add_a_tool_or_action`: facts son JSON datos; mensaje system distinto del intérprete, no tools. `test_timeout_refusal_incomplete_invalid_and_http_failure`: timeout total20s/connect2s, role/refusal/done_reason inválidos/JSON extra/proxies/redirect =>None, cierre de cliente. `test_oversized_snapshot_skips_http`: no peticiones cuando excede presupuesto. `test_no_input_or_raw_error_leaks`: sin logs de cuerpos/credenciales.
- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_ollama_replies.py -q`; RED ausente.
- [ ] **Step 3:** Implementar petición separada sin tocar schema/API del intérprete; `asyncio.timeout(20.0)` e httpx connect2, trust_envFalse/follow_redirectsFalse; ninguna excepción ordinaria sale del boundary, `CancelledError` sí propaga para recuperación. Prompt español pide breve/legible, composición/token coverage, gramática aprobada de Task2, cero compras/acciones inventadas; facts como datos, sin instrucciones de ellas.
- [ ] **Step 4:** GREEN focused + legacy Ollama, full/Ruff/diff y commit `feat: draft local Gemma replies from presentation snapshots`.

### Task 5: Orquestación y recuperación en Conversation/runtime

**Files:** Modify `conversation.py`, `runtime.py`; Test `tests/test_reply_conversation.py`, `tests/test_reply_runtime.py`; reutilizar helpers sintéticos existentes sin cambiar defaults de tests previos.

**Interfaces:** `Conversation(repo, interpreter, *, clock=None, reply_writer: ReplyWriter | None = None)`. Al construir runtime para proveedor ollama, inyectar `OllamaReplyWriter(settings.ollama_model)`; otros proveedoresNone. `handle` conserva firma y Reply.

- [ ] **Step 1: RED tests.** `test_closed_quantity_uses_writer_not_interpreter`: respuesta2 cambia una vez y writer recibe resultado guardado. `test_all_natural_classes_reach_writer`: incluidas product/list/cancel/clarify/replacement y respuestas cerradas. `test_slash_purchase_and_notices_bypass_writer`: mismos Replies y no llamada, incluso compra incompleta. `test_recover_prepared_before_any_interpretation`: writer ausente tras reinicio finalizafallback sin reducer/interpreter, sin renovarTTL. `test_cancel_between_commits_and_replay_after_finalization`: cancelar writer deja prepared; reiniciar recupera; completed devuelve texto idéntico y outbox único. `test_mutated_store_after_prepare_does_not_change_facts`: snapshot inmutable. `test_failed_writer_or_validation_uses_clear_fallback`: completed/outbox final correcto. `test_no_write_transaction_during_http`: writer puede abrir escritura en segundo repo temp sin bloqueo. `test_fake_runtime_does_not_call_stores_or_orders`: zeroorders, owner extranjero rechazado antes de draft.
- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_reply_conversation.py tests/test_reply_runtime.py -q`; expected RED constructor/ruta ausente.
- [ ] **Step 3:** Al principio handle validar inbox y completed; después prepared, antes de clasificar/model. Nueva petición natural con writer =>prepare/draft/validate/finalize; slash o compra autorizada =>apply_dialogue actual. Un prepared previo se recupera aunque ahora writerNone. No capturar errores SQLite/propietario como si fueran fallos del modelo. Rechazo de draft=>fallback una vez; `CancelledError` deja pending recuperable. Sin cambios en loop Telegram ni envío at-least-once, sin garantía de entrega exactamente una vez. Tiempo de presentación no renueva contexto.
- [ ] **Step 4:** GREEN focused + dialogue/end-to-end/runtime regression; full/Ruff/diff.
- [ ] **Step 5:** Commit `feat: recover generated replies without replaying shopping changes`.

### Task 6: Probe real, claridad y documentación de aceptación

**Files:** Create `scripts/Probe-Replies.ps1`, `tests/test_reply_probe.py`, `docs/superpowers/prueba-respuestas-gemma-2026-10-08.md`; Modify `docs/setup.md`, `docs/superpowers/progress.md`.

**Interfaces:** Probe opt-in desde worktree, defaults modelgemma4:e2b y loopback existente, sin settings privados. Modes `-Offline` (writer fake válido) y `-OfflineReject` (fake rechazado); real por defecto. Exit0 PASS,1 cualquier expectativa/claridad fallida,2 servicio/modelo no disponible. Cleanup solo temp root creado por el script.

- [ ] **Step 1: RED subprocess tests.** `test_probe_offline_pass_and_rejection_fallback`: ejecutar modos con DB temporal y sentinel de config privada sin lectura; exit0 con20escenarios comprobados, zeroorders y temp retirado. `test_probe_failed_expectation_exit_one`: introducir fixture de inconsistencia en modo test explícito, exit1 conserva todos los fallos. `test_unavailable_service_exit_two`: Mock loopback no disponible, no crear servicios/instalar modelos. No assert únicamente strings de código fuente.
- [ ] **Step 2:** Run `.venv\Scripts\python.exe -m pytest tests/test_reply_probe.py -q`; RED script/contrato ausente.
- [ ] **Step 3:** Implementar 20escenarios independientes: (1) arroz1+2 duplicado, (2) select entry, (3/4) known/unknown quantity, (5/6) alta sin/con cantidad, (7) mention add, (8) replace confirm, (9) replace quantity, (10) replace duplicate, (11/12) cancel proposal/no proposal, (13) expiry, (14) stale ref, (15) reserved, (16) natural list, (17) product known con nombre malicioso como dato, (18) product unknown, (19) invalid draft, (20) timeout. Los fallos del escritor se inyectan sin esconder resultados reales. Para pruebas reales correr18escenarios normales y2errores inyectados, distinguir generación del respaldo. Registrar texto completo inventado, aceptación de validador, fallback por clase, input/output latency, todas las expectativas de facts/options/inbox/outbox/TTL y zeroorders. Un probe no debe marcar PASS de calidad porque todos los mensajes usaron fallback: exigir draft aceptado en arroz duplicado, alta, cantidad, mention, confirmreplace y cancel; el resto reportado individualmente. Revisar legibilidad manual y publicar observaciones; si una clase falla, diagnóstico+RED/fix/re-review antes de afirmar aceptación, nunca relajar seguridad silenciosamente.
- [ ] **Step 4:** GREEN subprocess + full/Ruff/diff; ejecutar probe real solo contra servicio existente y DB inventada. Si servicio no disponible, marcar PENDIENTE sin descargas/reinicio. Evidencia clara antes/después y limitaciones semánticas/latencia, no afirmar aceptación Telegram. Documentar respaldo mejorado y recuperación preparada, comandos unchanged.
- [ ] **Step 5:** Commit `test: verify grounded Gemma replies and crash recovery`.

## Revisión y entrega

- [ ] Revisión independiente del rango completo, foco en crash-between-commits y contenido falso con tokens correctos; reparar Important/Critical con RED y re-review.
- [ ] Verificación fresca fullpytest/Ruff/diff/status; ledger con decisiones, IDs de commits, revisión y probe.
- [ ] Explicar al usuario qué generó realmente Gemma y qué cayó a respaldo; no atribuir texto determinista a generación.
- [ ] Pedir autorización separada para push/actualizar PR o prueba en Telegram privado; preservar el worktree y bot en marcha.
