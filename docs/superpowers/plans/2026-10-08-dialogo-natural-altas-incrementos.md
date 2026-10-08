# Diálogo natural, altas pendientes e incrementos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Saludos sin consultas accidentales, altas sin filas incompletas e incrementos confirmados, con respuestas específicas y aceptación real de la secuencia del usuario.

**Architecture:** Reconocimiento de petición completa + propuesta no fiable de Gemma, reducer con estados separados de alta/incremento, y mutaciones revalidadas en SQLite. Mantener prepare/finalize y recuperación de presentaciones v1; introducir presentación v2 con variantes por acto y sin cabecera genérica. Todo se implementa en un worktree nuevo, no en el checkout que alimenta el bot.

**Tech Stack:** Python/Pydantic/SQLite/httpx/Ollama/pytest/PowerShell existentes, sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-10-08-dialogo-natural-altas-incrementos-design.md` (aprobada).

## Global Constraints

- «La lista privada existente NO se limpia ni consolida automáticamente.»
- «No se añade compra autónoma, conversión de unidades, sumas entre entradas, autocorrección general de productos, asistente general ni conversación externa.»
- «Un alta sin cantidad permanece fuera de la lista como propuesta pendiente.»
- «Saludo + una compra no otorga nueva autorización.»
- «Generación/replay/saludo/consulta no renuevan el TTL»; son exactamente 900 segundos de inactividad de transiciones válidas.
- «Un trabajo de presentación v7 ya preparado implica una acción guardada: se recupera y finaliza con su instantánea compatible».
- «No HTTP durante transacciones.»
- «Nada que escriba el redactor es ejecutable.»
- «La aprobación de esta especificación permite escribir el plan; la del plan y su método permite implementarlo.»
- Sin private/, Telegram/tiendas reales, compras, cambio de ACL de usuario, reinicios, downloads, unload forzado, merge/push/PR no autorizados. Regresiones existentes en recursos temporales sí permitidas.

## Review Focus

- Alta pendiente que coincide con un producto añadido por otra actualización: perder permiso anterior y preguntar duplicados antes de guardar (Task 2).
- «Hola, necesito arroz» frente a «Arroz Hola» y «hola /comprar»: quitar solo prefijo social de peticiones admitidas, nunca otorgar permisos (Task 1/5).
- Confirmación tras cambiar base/revisión/reserva: no recalcular bajo el sí antiguo ni sumar dos veces (Task 3).
- Migración con presentación v1 preparada y diálogo viejo: finalizar hechos históricos sin rehacer/convertir la operación (Task 2/5).
- Todo parece correcto porque el intérprete del probe es fake o la redacción usa respaldo: exigir propuestas reales y medir ambas llamadas (Task 6).

## Archivos / responsabilidades

- `dialogue_requests.py`: reconocimiento completo y comprobación de propuestas, separado del reducer.
- `dialogue.py`, `domain.py`: contratos nuevos, estados estrictos, respuestas cerradas y rango SQLite.
- `dialogue_additions.py`: transiciones de borrador/alta/cancelación, sin I/O.
- `dialogue_increments.py`: selección, cantidad adicional, confirmación y cálculo, sin I/O.
- `dialogue_controller.py`: orquestar helpers y preservar sustitución/comandos existentes; extraer lógica tocada, no duplicarla.
- `dialogue_storage.py`, `storage.py`, `migrations/008.sql`: guardas finales/migración; sin checkout nuevo.
- `presentation.py`, `presentation_replies.py`, `presentation_validation.py`, `ollama_replies.py`: v1 compatible, v2 por acto; `dialogue_replies.py` respalda también proveedor sin redactor.
- `conversation.py`, `ollama_interpreter.py`: clasificación/precedencia y esquema de propuestas derivado de fuente, sin permisos nuevos del modelo.
- Tests por responsabilidad, `scripts/Probe-NaturalDialogue.ps1`, docs y evidencia.

## Interfaces compartidas (exactas)

Contratos heredan Model strict/frozen/extra-forbidden; persistencia revalida JSON incluyendo model_copy. `PackageQuantity` conserva 1..9223372036854775807. Ningún flag de permiso entra en Intent ni payload del modelo.

```text
SourceRequest(action: Literal['greet','add','mention_product','increment','list','product_query'],
    description: str | None = None)
classify_request(text: str) -> SourceRequest | None
validate_request(text: str, proposal: Intent, lines: list[ListLine]) -> Intent
```

Añadir `greet`/`increment` a Intent.action; no nuevas cantidades/IDs model-authorized. Mantener wrapper `literal_request(text)` para callers antiguos: solo add/mention compatibles, delegando gramática al nuevo módulo. `dialogue_controller.validate_model` delega en validate_request. No repetir regex en Ollama y controller.

Estado v2: añadir `version: Literal[2]=2`, `pending_kind: Literal['add','increment'] | None=None`, `base_quantity: PackageQuantity | None=None`, `additional_quantity: PackageQuantity | None=None`, `increment_confirmed: bool=False`. Preguntas nuevas `add_quantity`, `increment_quantity`, `confirm_increment`, `increment_missing`, `increment_unknown`; reutilizar select_line con pending_kind para siguiente pregunta. `proposal_quantity` es total propuesto, no delta. Respuestas nuevas `reject` (no ante confirm_increment), y opciones de preguntas nuevas usando claves add/change_quantity existentes.

Mutation nueva `kind='increment'`, `expected_base: PackageQuantity | None`, `additional_quantity: PackageQuantity | None`; `quantity` es total final. Validar identidad y aritmética para esta kind; no SQL aditivo. Decision reply_kind añade `pending_add`, `greeting`, `incremented`. Mutación y legacy_intent siguen excluyentes.

```text
begin_addition(state: DialogueState, lines: list[ListLine], *, now: datetime) -> DialogueDecision
answer_addition(answer: DialogueAnswer, state: DialogueState,
    lines: list[ListLine], *, now: datetime) -> DialogueDecision
begin_increment(focus: ProductMention, lines: list[ListLine], reserved_ids: frozenset[str],
    *, user_id: int, chat_id: int, now: datetime) -> DialogueDecision
answer_increment(answer: DialogueAnswer, state: DialogueState, lines: list[ListLine],
    reserved_ids: frozenset[str], *, now: datetime) -> DialogueDecision
```

Reutilizar referencia, canonicalización, stale/expiry y renovación de estado existentes; no duplicar lógica de autorización en helpers. Helper solo recibe referencias ya revalidadas o devuelve rechazo explícito, nunca selecciona una fila implícitamente.

## Preparación

- [ ] Verificar checkout/HEAD y notas del plan; crear ledger de este plan, interfaces y decisiones. No repetir tareas del plan anterior.
- [ ] Crear worktree nuevo `feat/natural-dialogue` desde el checkout aprobado con spec/plan; no reutilizar worktree gemma antiguo (no contiene estos documentos) ni modificar código del bot en ejecución. Usar entorno Python existente sin instalar dependencias; PYTHONPATH explícito al nuevo worktree cuando se use el Python compartido, comprobar imports desde allí.
- [ ] Baseline pytest/Ruff, estado limpio. Registrar todas las pruebas/commits/revisiones por tarea.

### Task 1: Peticiones completas, saludos y frontera del modelo

**Files:** Create `dialogue_requests.py`, `tests/test_dialogue_requests.py`; Modify `domain.py`, `dialogue_controller.py`, `ollama_interpreter.py`, `pyproject.toml`.

**Interfaces:** Produce SourceRequest/classify_request/validate_request y wrappers indicados arriba. Extender Intent solo con greet/increment. Consume parse_command/normalized/canonical_name/product-query guards; conservar legado parse y parse_with_context.

- [ ] **Step 1: RED tests**, sin llamadas reales. Ejemplo de contrato:
  ```python
  def test_more_is_not_a_literal_product():
      request = classify_request('quiero mas arroz')
      assert request.action == 'increment'
      assert request.description == 'arroz'
  ```
  `test_greeting_is_not_list`: hols/hola/holaqué tal/buenas y modelo propone list => propuesta rechazada, no lista. `test_whole_list_request_required`: dame mi lista/qué hay en mi lista aceptados; holaqué tal/«mi lista» citado/negado/condicional rechazados. `test_social_prefix_keeps_literal_name`: Hola, necesito Arroz Integral => nombre exacto; Arroz Hola no saludo; hola /comprar no buy. `test_modifier_is_not_removed_from_variants`: quiero más arroz integral =>increment+nombreíntegro; necesito Arroz Más =>addliteral; descripción ambigua/quoted no incremento. `test_source_constrained_ollama_schema`: requestformat usa action/description/nullqty de la fuente también para increment, devuelveclarify en salida incompatible.
- [ ] **Step 2:** `python -m pytest tests/test_dialogue_requests.py -q` => RED por ausencia/aceptación list errónea. Usar Python/import path del worktree, no root.
- [ ] **Step 3:** Gramática fuente explícita: greet completo {hola,hols,buenas,buenos días,hola qué tal,qué tal}, puntuación exterior y acentos/caso normalizados. Prefijo social solo `hola[, ]` seguido de petición no slash no compra reconocida. Incremento entero `quiero más X`/`añade más X`, sin número inicial en esta entrega; X conserva variantes y la protección contra condiciones/negaciones/múltiplesproductos/URLs existente. List completo {lista,qué hay en la lista,qué hay en mi lista,muestra la lista,muestra mi lista,dame mi lista}. Guardar texto original; no reconstruct nombres normalizados. Model list no reconocido =>clarify. No eliminar prefijos de compras ni modificar IncomingMessage durable.
- [ ] **Step 4:** GREEN focused + Ollama/interpreter/conversation regresiones, full/Ruff/diff antes de commit. Natural increment aún no ejecuta nada hasta Task3.
- [ ] **Step 5:** Commit `feat: ground social and incremental requests in complete user messages`.

### Task 2: Estado v2, migración v8 y alta pendiente

**Files:** Create `dialogue_additions.py`, `migrations/008.sql`, `tests/test_pending_additions.py`; Modify `dialogue.py`, `dialogue_controller.py`, `dialogue_storage.py`, `storage.py`, `dialogue_replies.py`, `pyproject.toml`; actualizar tests que esperan la antigua alta con quantityNULL solo cuando se sustituye su expectativa deliberadamente.

**Interfaces:** Produce modelos de estado/mutación/decisión compartidos, begin_addition/answer_addition. `quantity` existente actualiza fila guardada; `add_quantity` crea fila al recibir cantidad. Mantener APIs públicas Repository y build_presentation.

- [ ] **Step 1: RED tests** con Repo real temp. `test_pending_add_not_visible_and_cancel_discards`: nuevo producto sin cantidad =>0filas, preguntaadd_quantity, /lista no incluye borrador, cancelar=>0filas. `test_quantity_commits_once`: 2=>1fila qty2 y replay no duplica. `test_pending_survives_list_greeting_restart_not_expiry`: estado/timestamps idénticos tras list/saludo, reinicio vigente, a900s respuesta2 no guarda. `test_duplicates_appearing_after_question_need_new_permission`: otro update añade coincidente, cantidad no guarda sin nueva elección. `test_slash_add_pending_but_complete_add_direct`: /anadir arroz pendiente, /anadir2arroz y añade2arroz guardan con valida duplicados. `test_legacy_unknown_row_remains_saved`: fixture anterior sigue visible y se actualiza solo con ref autorizada. `test_v8_preserves_rows_and_prepared_v1`: tablasdurables intactas, old dialogue_state vacío, v1job recuperable sin cambioqty/revisión; migrate2veces, reject9.
- [ ] **Step 2:** `python -m pytest tests/test_pending_additions.py -q` => RED por filas guardadas prematuramente/v7.
- [ ] **Step 3:** Migración BEGIN/COMMIT borra solo dialogue_state y user_version8; no toca presentation_jobs ni filas históricas. Validación de estado: addpending focus.line/targetNone, sin flags increment; confirm_increment exige target/base/delta/proposal totalcoherente; estados legacy quantity tienen pending_kindNone. Implementar renovación900s solo en transición válida, consultas/greet conservan estado tal cual. Nuevos pedidos completos sustituyen borrador; propuestas malformadas no lo borran. Duplicar otra entrada sigue pidiendo cantidad si no hay; no reutilizar una quantity ajena. Guardar add solo conqtyválida en reducer y limpiar pending_kind en el mismo rebound que asigna el ID real después de insertar; no persistir addpending con focus.line guardada. No cambiar `Repository.apply_intent` legacy usado para fixtures/operaciones internas. Estado antiguo preparado no se reaplica, presentación vieja devuelve guardado/fallback. Documentar aclaración de actualización «El contexto anterior ha caducado; repite la petición»; no fabricar un outbox de migración ni afirmar pérdida de productos.
- [ ] **Step 4:** GREEN focused + storage/dialogue/replacement/reply recovery/regresiones (actualizar fixtures para esperar borrador nuevo, no eliminar tests), full/Ruff/diff.
- [ ] **Step 5:** Commit `feat: keep incomplete additions pending outside the shopping list`.

### Task 3: Incrementos seleccionados y confirmados

**Files:** Create `dialogue_increments.py`, `tests/test_dialogue_increments.py`; Modify `dialogue.py` (parser respuestas), `dialogue_controller.py`, `dialogue_storage.py`, `dialogue_replies.py`, `interpreter.py` (conversión de cantidad acotada), `pyproject.toml`.

**Interfaces:** Produce begin_increment/answer_increment. Consume state v2 y mutationkindincrement; SQL totalsetter guardado, sin arithmetic/modelpermissions nuevos.

- [ ] **Step 1: RED tests**: `test_two_rice_entries_select_then_delta_then_confirm`: rice1/rice2/integralNULL =>select solo2rice; selecciona1,2adicional=>confirm1+2=3, noescritura hasta sí, resultadoqty3/revision+1. `test_missing_product_offers_pending_add`:0matching=>increment_missing con opciónadd, nofila; elegiradd inicia add_quantity. `test_unknown_base_offers_total_not_zero`:NULL=>increment_unknown, opciónchange_quantity=>quantityexisting, no sum0. `test_no_cancel_and_expired_do_not_write`: confirm no/cancelar/900s deja filas idénticas. `test_changed_base_missing_or_reserved_invalidates_yes`: actualizaciones con mismorev corruptaqty, revisionchanged/deleted/reservation => noinc; no reajustar total bajo sí anterior. `test_overflow_units_and_diaper_packs`: max+1, 5000digits, fracción/kg/unidades sinpackage=>clarify completa sincrash; explicit2paquetes admitido. `test_replay_rollback_and_snapshot_unchanged`: replayconfirm/injectedoutboxabort/retry revisionuna, pedidos históricos intactos.
- [ ] **Step 2:** `python -m pytest tests/test_dialogue_increments.py -q` => RED por transición/guardausente.
- [ ] **Step 3:** Exactmatchescanonicaldescription no fuzzy/no integralautoselect; selecciónincluyeqty. baseconocida recibe deltaPackageQuantity, calcula base+delta<=max por aplicación. guardar confirmstatecon ref/base/delta/total; `sí`/`confirmo` exige confirm_increment; `no`=reject; cantidad no confirma. Unknownbase/missing choices explícitas usando respuestasconkeys add/change_quantity según pregunta. Resolver stale/reserved antes de closedanswer. En storage nueva rama explícita increment (else ya no significa replace): comparar refrevision/base/reservations/state.confirmed y sum==total; UPDATE quantity=?,revision=revision+1 WHEREid/revision/quantity yNOTreserved, rowcount1; source/description/productid intactos. Después limpiar todos los camposincrement y dejarfocusnuevo ref, sin permiso reusado. No confiar solo en bandera serializada de modelo ni convertir unknownbase a0. En interpreter producir `_package_count(text: str) -> int | None`, capturar ValueError/conversión excesiva y exigir1..MAX_QUANTITY; usar en ramas /cantidad/altas numéricas en lugar de int sin guardas, devolver clarify sin excepción y sin mutación.
- [ ] **Step 4:** GREEN focused + pending/replacement/quantityboundary/storage/full/Ruff/diff; confirmar límites de todas las entradas numéricas, incluyendo intconversioncommands ya alcanzable, sin saltarse overflow con fixtures.
- [ ] **Step 5:** Commit `feat: confirm incremental quantities against current unreserved rows`.

### Task 4: Presentación v2 por acto, sin introducción rutinaria

**Files:** Create `presentation_phrases.py`, `tests/test_natural_presentation.py`; Modify `presentation.py`, `presentation_replies.py`, `presentation_validation.py`, `ollama_replies.py`, `dialogue_replies.py`, `pyproject.toml`.

**Interfaces:** `PresentationSnapshot.version: Literal[1,2]`; añadir `act: Literal['greeting','pending_add','select_entry','increment_amount','increment_confirm','increment_missing','increment_unknown','result','list','cancel','clarify'] | None=None`, `phrases: tuple[PresentationPhrase,...]=()`. PresentationKind añade greeting/pending_add/incremented para v2. `PresentationPhrase(key: str, role: Literal['fact','question','option'], variants: tuple[str,...])`; variants usan solo referencias existentes {{fN}}/{{q}}/{{oN}}, sin valores copiados, salvo las dos frases sociales sin datos autorizadas abajo. v1 conserva serialización/validación viejas y rechaza act/phrases no vacíos o kindnuevo; v2 requiere act y phrasescoherentes. Producir `presentation_variants(snapshot: PresentationSnapshot) -> tuple[PresentationPhrase,...]` en nuevo módulo; `public_presentation(snapshot: PresentationSnapshot) -> dict` en presentation.py excluye siempre fallback, y para v1 también act/phrases. Writer/budget usan el mismo serializador público compacto para no variar contratos/límites v1. Las APIs draft/validate/build y Reply permanecen.

- [ ] **Step 1: RED tests**. `test_greeting_and_cancel_do_not_have_generic_lead`: ninguna salida contiene Aquí tienes el detalle/Vamosporpartes/Te loexplico; greet jamás contiene filas. `test_pending_quantity_question_not_total_update`: «¿Cuántos envases de arroz quieres añadir?» no fraseincrement en alta. `test_increment_question_and_arithmetic_coverage`: nombrebase/delta/total completos, opciones sí/no/cancel compatibles; no éxito sinmutación. `test_list_bullets_without_selection_ordinals`: solo listar viñetas, ordinales si selección. `test_phrase_schema_and_validator_agree`: enumerar todas las variantes emitidas para cadaact, accepted, y tamperednúmero/negación/tokenopción falsa rechazadas. `test_hostile_names_are_literal_not_grammar`: token-looking nombre no cambia branchschema. `test_v1_prepared_snapshot_still_reads_and_composes`: bytescontractviejo read/fallback/idremoval y budgets intactos.
- [ ] **Step 2:** `python -m pytest tests/test_natural_presentation.py -q` => RED v2/actoausente/cabeceravieja.
- [ ] **Step 3:** v2 prohíbe rolelead, incluso si es una de las5viejasfrases. Humanizar datos en application facts: producto/unidad singularplural, estadoantesdelcommit explícito. `{{q}}` guarda pregunta clara poracto; variantes de question permitidas exactas `{{q}}`, `{{q}} Puedes cancelar.` solo en estados cancelables; opcionvariants `{{oN}}` o `• {{oN}}`; factualvariant `{{fN}}` o `• {{fN}}` solo para list/selection. Result/cancel/greet sin bullets. Saludo fact autorizado variantecontextual elegida por el modelo entre «¡Hola! ¿En qué te ayudo con tu lista?» y «¡Hola! ¿Qué necesitas para tu lista?»; única frase social exacta en rolefact cubre la clave f0 sin sustituir productos, únicamente actgreeting y snapshot sin filas/opciones. Ninguna otra cadena libre cubre hechos. Publicpayload v2 incluye phrasescontract, excluyefallback/privateIDs; schema exactbranches condicionadas, espacios/puntuación literales validados antes de sustituirdatos. Permitir variantes equivalentes de aplicación poracto, no llamar a selección de formas predefinidas «prosa libre». Los valores quedan anclados; no elevar la gramática arbitrariamente para mejorar acceptancerate. Mantener20facts/10options/8000charscontext/2000draft/6000final/20sHTTP/connect2; v1recovery usagrammáticaanterior, v2 nunca añadecabecera genérica. Los facts de confirmación aritmética contienen base/delta/total obligatorios; opciones siempre mismoorden, nunca omitir/repetir referencias por variar phrasing.
- [ ] **Step 4:** GREEN focused + v1/ollamawriter/presentation/recovery/full/Ruff/diff. Medir schema size y aceptación actual; alternativas no causan saltarse presupuesto/truncación. Scalarfallback mismassemánticas sinconfusión porproveedor.
- [ ] **Step 5:** Commit `feat: present dialogue acts without repetitive generic introductions`.

### Task 5: Conversación integrada, contexto preservado y recuperación

**Files:** Modify `conversation.py`, `ollama_interpreter.py`, `presentation_storage.py` solo si necesita validar v2; Create `tests/test_natural_dialogue_runtime.py`; helpers en `tests/dialogue_support.py` (añadir writer optional sin alterar defaultsemantics).

**Interfaces:** Consume classify/validate y estados/reducer/storage/views; firmas Conversation.handle/Repository.prepare/finalize sin cambios. Runtimeproveedor/inyección existentes se reutilizan.

- [ ] **Step 1: RED integración** FakeBot/SQLite real/MockTransport para outputs y errores. `test_capture_sequence_has_no_accidental_list_or_more_product`: hols/holaqué tal no list; quiero mas arroz nofila masarroz; cancelar/listfinaligual3filas. `test_pending_add_list_greeting_resume`: nuevoX pendiente, list/greet no borran ni renewtimestamps;2=>únicafila. `test_compound_greeting_and_hostile_list_proposal`: hola necesitoarrozválido, hostileIntentlistantehola nuncaconsulta. `test_commands_buy_and_other_providers_unchanged_authority`: slashfixedformat, compraautorizaciónsinstrip, OpenAI/commandsonly notgeneratejobs; pendingadd semantics nuevo sí aplica. `test_migrate_prepared_v1_recover_without_writer`: v7 preparedacciónya guardada, v8dialogueclear, recuperar sin interpreter/reducer/otra escritura, exactReply/outboxúnico. `test_crashes_around_add_and_increment_commits`: cancelHTTP/callbackoutboxerror/restart/replay no doblewrite niTTLrenew. `test_owner_and_corrupt_state_fail_closed`: nada enviado/drafteado paraforeignowner.
- [ ] **Step 2:** `python -m pytest tests/test_natural_dialogue_runtime.py -q` => RED en secuencia/contexto, no una fixturefalse.
- [ ] **Step 3:** Completed/preparedlookup sigue primero. Saludo puro reconocido produce Intentgreet confiable desde fuente sin intérpreteHTTP; publicación usa writer y no lista. Requestsincrement preceden aliasparse_command que antescapturaba «más arroz»; slash y compraautorizada mantienenprioridad. Los demás nuevosrequests usan Gemmapropuesta+validate y revalidacióntransaccional. NostripmutanteIncomingMessage. list/productquery no modifican ni renew borrador; nuevaspeticionescompletas sí reemplazan; serdeestricta compatv1/v2jobs. ErroresSQLite/owner no atrapadoscomo fallomodelo; CancelledErrorprepared recuperable.
- [ ] **Step 4:** GREEN focused/regresiones todasclases/full/Ruff/diff. No cambiar mocks para ocultarnuevanetworkboundary; agregartripwire y ambasMockTransport cuando sea necesario.
- [ ] **Step 5:** Commit `feat: preserve pending dialogue across social turns and queries`.

### Task 6: Aceptación de interpretación y respuesta con Gemma real

**Files:** Create `scripts/Probe-NaturalDialogue.ps1`, `tests/test_natural_dialogue_probe.py`, `docs/superpowers/prueba-dialogo-natural-2026-10-08.md`; Modify `docs/setup.md`, `docs/superpowers/progress.md`.

**Interfaces:** Probe opt-in existingloopback/gemma4:e2b/tempSQLite, reales OllamaInterpreter + OllamaReplyWriter + Conversation/Repo; salutos/closes/aliases deterministas se etiquetan como tales, NO intérpretefake en realmode. Offlinefixturepara subprocess separado. Exit0PASS,1expectativa/qualityFAIL,2servicio/modelausente; cleanup deltempcreado.

- [ ] **Step 1: RED subprocess** `test_real_mode_does_not_substitute_interpreter`: injected localtransport inspecciona ambos tipos de request para add/increment/list y autoridad/guard posterior; sin usarfakeproposals enmodereal. `test_offline_exit_cleanup_and_unknown_error_metrics`: realexit0/1/2, sentinelprivado nuncaabierto y cleanup, failurescon ordersnullsi noquery. `test_quality_cannot_pass_fallback_only`: requiredclassesdeinterpretation y redacción fallan enrespuesta incompatible aunquefallbacksea seguro. No tests por stringsdescriptivas de source.
- [ ] **Step 2:** `python -m pytest tests/test_natural_dialogue_probe.py -q` => RED scriptausente/contrato noimplementado.
- [ ] **Step 3:** Tres secuencias independientes con fixtures arroz1,arroz2,integralNULL ysin órdenes: A capturaexacta `[hols, hola que tal, quiero mas arroz, cancelar, dame mi lista]` =>lista siempre3, no masarroz, sin list en saludos. B `[necesito avena, dame mi lista, hola, cancelar, necesito avena, 2, dame mi lista]` =>0avenahastaúltimo2, luegoúnicaqty2. C `[quiero más arroz, 1, 2, no, quiero más arroz, 1, 2, sí, dame mi lista]` =>rice1hasta sí, luego3, rice2eIntegral intactos. Reingresar mismo updateconfirm para replay; reiniciar Conversation entre cantidad/confirm e incluir expiry/reserved/changedrevision escenarios adicionales sintéticos separados. Registrar originalinput, si determinista/modelcall, proposedIntent, actualsavedstate/list, modeloWriterraw/accepted/fallback, latenciasambasllamadas y total; no inferirquality a partir de nuestraspropiasplantillas. PASS exige todasexpectativas y modelos reales compatibles en increment/add/list donde llamados; greet no modelintent por diseño. Aclarar alcance de redacción poracto, no atribuir hechosfijos a modelogenerado. Usar existingservice sin descargar/reiniciar ni forzar frío.
- [ ] **Step 4:** GREEN subprocess/plainfull/Ruff/diff. Ejecutarprobe real y repetir solo tras resultado corregidoPASS; unavailable=>PENDIENTE. Si falla realinterpretación/tuple-schema, systematicdebugging+REDantesdefix; no relajar seguridad, copiar salida ni cambiarexpectativaspara fabricarPASS. Documentar frasereal/cancelación/migración/restart y preservar fallos antes/después. Telegramprivadoaceptación sigueautorizadaaparte.
- [ ] **Step 5:** Commit `test: replay natural shopping conversations with real local Gemma`.

## Revisión y entrega

- [ ] Revisión independiente por tarea y finalrange, con foco en semántica de los sí/cancelar, compatpreparedv1 y fronterasnuméricas. Important/Critical se reproducen/fijan/re-revisan.
- [ ] Fullpytest/Ruff/diff/status frescos sobre HEADentregado; evidencia de modelos reales separada de tests offline.
- [ ] No merge/push/PR/restart/limpieza de lista sin decisión posterior. Presentar worktree/rama y cómo probar cuando autorice el usuario.
