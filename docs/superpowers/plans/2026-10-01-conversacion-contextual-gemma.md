# Conversación contextual con Gemma Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mantener el hilo de lista/fichas, resolver referencias y cantidades, y permitir sustituciones confirmadas sin delegar escrituras o compras a Gemma.

**Architecture:** Un controlador puro decide transiciones sobre estado estructurado con caducidad; un mixin de Repository aplica sus decisiones dentro de la transacción de inbox/outbox. Conversation conserva comandos prioritarios y obtiene propuestas de Gemma con contexto acotado. Las respuestas se construyen desde el resultado guardado.

**Tech Stack:** Python 3.12+, Pydantic 2, SQLite, pytest/Ruff, httpx/Ollama local existente; no nuevas dependencias.

**Spec:** `docs/superpowers/specs/2026-10-01-conversacion-contextual-gemma-design.md` (aprobada por el usuario).

## Global Constraints

- «SQLite sigue siendo la fuente de verdad. Gemma propone interpretaciones, no decide qué modificar.»
- «No autoriza reiniciar el bot privado, cambiar configuración, hacer merge o push.»
- «La nueva memoria nunca sirve para autorizar compras o reanudar órdenes.»
- «No se añade soporte para kilos, litros, fracciones ni conversiones de piezas a envases: las cantidades siguen siendo enteros positivos de envases.»
- «El estado caduca a los **15 minutos de inactividad**.»
- «Cada respuesta válida al diálogo renueva el plazo; un replay no lo renueva.»
- «No se corrigen automáticamente erratas en nombres de productos ni se interpretan términos desconocidos como cortesía prescindible.»
- «Una cantidad responde solo al producto preguntado.»
- «Para pañales sigue siendo obligatorio escribir paquetes/envases explícitos, incluso si hay contexto (“2 paquetes”).»
- «Si la línea desapareció, cambió de revisión o está reservada por una orden, no sustituir.»
- «Replay del mismo update devuelve la respuesta original y no duplica altas, confirmaciones, backlog, revisiones ni renovaciones del plazo.»
- Conservar permisos privados/identidad/offset y capacidades live; no red de tiendas, scraping, compras, modelo externo ni descarga. Pruebas solo con datos temporales inventados.

## Review Focus

1. Orden de rutas: «añade eso»/«añádelo» no se guardan como productos; slash y autorización de compra no heredan permiso del foco. Test en Task 3.
2. Foco obsoleto: un reinicio, consulta intermedia, selección numérica o cambio de revisión no convierten «2»/«sí» en otra acción. Tests en Tasks 3/4/6.
3. Equivalencia demasiado amplia: variantes con mismo product_id o un destino ya existente no se fusionan/suman; ninguna coincidencia elimina calificadores. Tests en Tasks 3/4.
4. Fracaso parcial: outbox rechazado, migración vieja o replay de confirmación no dejan sustitución/estado a medias. Tests en Tasks 2/4/6.
5. Modelo adverso/contexto truncado: no elegir IDs/revisiones del modelo ni ejecutar cantidades/sustituciones desde su salida, aunque haya un foco válido. Tests en Tasks 3/5/6.

---

## Estructura y decisiones de interfaces

Mantener layout plano y patrón existente de mixins (`checkout_storage.py`). No reorganizar checkout/storage ajenos al flujo de diálogo.

| Archivo | Responsabilidad |
| --- | --- |
| `dialogue.py` (nuevo) | Contratos estrictos, reloj/caducidad, nombres equivalentes y respuestas cerradas; ninguna DB/red. |
| `dialogue_controller.py` (nuevo) | Reducer puro: validar propuesta contra texto/estado/filas y decidir transición/mutación. |
| `dialogue_replies.py` (nuevo) | Texto determinista desde decisiones y filas realmente guardadas; lista natural sin UUID. |
| `dialogue_storage.py` (nuevo) | Estado por usuario/chat, validación de origen/revisión y transacción de aplicación. |
| `migrations/006.sql` (nuevo) | Tabla de diálogo, versión 6 y retirada segura de aclaraciones sin fecha. |
| `domain.py`, `conversation.py`, `storage.py` | Integración sin duplicar transacciones ni aceptar órdenes del modelo. |
| `ollama_interpreter.py` | Contexto de diálogo mínimo y propuestas de mención; sin historial libre. |
| `tests/dialogue_support.py` (nuevo) | Clock controlado, repositorio temporal y envío/inspección reutilizables; no helpers en producción. |
| `tests/test_dialogue*.py` (nuevos), tests actuales | Estado, controlador, persistencia, integración y regresiones. |

### Contratos compartidos (definidos en Task 1)

- `LineRef(Model)`: `id: str`, `revision: Positive`.
- `ProductMention(Model)`: `description: str`, `source_update_id: int`, `line: LineRef | None = None`, `unit: Literal['envases','paquetes','botes','sacos'] = 'envases'`.
- `DialogueState(Model)`: `user_id: int`, `chat_id: int`, `focus: ProductMention | None`, `target: LineRef | None = None`, `candidates: tuple[LineRef, ...] = ()`, `question: Question | None = None`, `options: tuple[str, ...] = ()`, `proposal_quantity: Positive | None = None`, `replacement_confirmed: bool = False`, `duplicate_confirmed: bool = False`, `updated_at: UtcTime`, `expires_at: UtcTime`.
- `Question`: `'add_or_replace' | 'duplicate_choice' | 'select_line' | 'quantity' | 'confirm_replace' | 'replace_quantity' | 'replace_duplicate' | 'remove_id'`. La última conserva el flujo técnico de quitar existente, no habilita remove del modelo.
- `DialogueAnswer(Model)`: `kind: Literal['add','replace','change_quantity','keep_quantity','quantity','confirm','select','remove_id','cancel']`, `quantity: Positive | None = None`, `unit: Literal['envases','paquetes','botes','sacos'] | None = None`, `selection: Positive | None = None`, `line_id: str | None = None`.
- `DialogueMutation(Model)`: `kind: Literal['add','set_quantity','replace']`, `description: str | None = None`, `quantity: Positive | None = None`, `target: LineRef | None = None`, `unit: Literal['envases','paquetes','botes','sacos'] = 'envases'`.
- `DialogueDecision(Model)`: `mutation: DialogueMutation | None`, `legacy_intent: Intent | None`, `state: DialogueState | None`, `prompt: str | None = None`, `reply_kind: Literal['clarify','added','updated','replaced','cancelled','natural_list','legacy']`. Mutación y legacy_intent son excluyentes; los modelos no reciben este esquema.

No duplicar descripción/cantidad actual dentro de candidatos: resolver `LineRef` contra filas vigentes. `focus.line` identifica la línea del producto mencionado; `target` identifica origen de sustitución o destino de cantidad. Los flags de confirmación son estado del controlador, nunca campos aceptados del modelo.

### Semántica concreta que evita decisiones ocultas

- Reloj inyectable UTC; `expires_at = now + timedelta(minutes=15)`, expirado si `now >= expires_at`. `dialogue_state` no escribe/renueva por leer. El reducer invalida un estado expirado al procesar el siguiente mensaje.
- `canonical_name` elimina diferencias de acentos/mayúsculas/espacios, no calificadores ni unidades/tallas. Coincidencia completa, no substring ni product_id.
- Después de una cantidad válida, conservar foco de esa línea con su revisión nueva y sin pregunta; habilita «ahora X». Consultar la lista no cambia foco ni renueva TTL. Consulta de ficha de otro producto deja solo una mención no ejecutable de ese producto y cancela pregunta incompatible; no hereda el destino anterior.
- Mientras hay varias opciones, un «sí» no selecciona nada. Solo confirma una pregunta `confirm_replace` o `replace_duplicate`; «no»/«cancelar» cancelan la propuesta. Nunca confirmar compra con estas respuestas.
- Selecciones numeradas se aceptan únicamente para opciones/candidatos ofrecidos por el bot. No mezclar su gramática con una cantidad pendiente; revalidar todos los candidatos/revisiones antes de interpretar el número.
- Una nueva petición completa puede sustituir una pregunta pendiente; un texto no interpretable conserva la pregunta sin renovar TTL y repite aclaración concreta. Consulta de otro tema no reutiliza permiso anterior.
- «Cancelar» sin pregunta/foco responde que no hay propuesta pendiente; no elimina líneas ni pasa por Ollama. La excepción segura puede producir answer cancel sin estado, pero ninguna respuesta que muta datos puede hacerlo.
- Sin foco, «ahora X» ofrece añadir X, no lo añade ni presume una línea origen. No usar pluralidades del modelo para inventar varios productos.
- Ante origen con cantidad desconocida, después de confirmar reemplazo pedir cantidad. Con cantidad previa conocida, ofrecer conservarla o indicar otra. No ejecutar hasta confirmar origen/destino y resolver cantidad y conflicto de duplicado.
- Conflicto de destino duplicado: ofrecer mantener líneas separadas con confirmación explícita o cancelar. No fusionar. Revalidar el conflicto dentro de la transacción final.
- Al aplicar un alta, el repositorio genera ID y vincula `focus.line` y, si hay pregunta de cantidad, `target` a la fila creada. Tras actualizar/sustituir, vuelve a vincularlos a la revisión real. No devolver referencias predictivas obsoletas.
- Etiquetas son presentación de un conteo de envases, no conversión: «2 paquetes» fija etiqueta paquetes; bare `2` conserva la etiqueta de la pregunta. No añadir columna a `list_lines`; fuera del contexto vigente se usa envases, sin inventar formato físico.
- `/lista` conserva IDs; consulta natural usa una lista sin IDs. `/anadir` pide confirmar duplicados, pero no llama al modelo. `/cantidad` fija total explícito. Quitar/compra/status/resume conservan ruta determinista previa, sin usar un foco de modelo como autorización.
- Una orden explícita incompleta puede conservar su pregunta de cantidad, pero contestarla nunca crea automáticamente una orden. Se sigue requiriendo una nueva autorización determinista de compra.

## Preparación (antes de Task 1)

- [ ] Verificar worktree existente `feat/gemma4-local`, limpio; no crear otro ni tocar el checkout raíz. Base documentada del plan: `6d45987`.
- [ ] Cargar TDD y verification-before-completion; ledger de este plan en `.superpowers/sdd/2026-10-01-conversacion-contextual-gemma/`. No reutilizar ledgers de planes anteriores.
- [ ] Baseline: `.venv\Scripts\python.exe -m pytest -q` → suite verde (última evidencia previa: 379 tests; obtener evidencia nueva). Si falla, investigar antes de ejecutar tareas.

### Task 1: Contratos y respuestas cerradas seguras

**Files:** crear `dialogue.py`, `tests/dialogue_support.py`, `tests/test_dialogue.py`; modificar `domain.py:Intent.action` y `pyproject.toml:py-modules` solo para el módulo creado.

**Interfaces:** produce contratos arriba y `DIALOGUE_TTL = timedelta(minutes=15)`, `canonical_name(text: str) -> str`, `expired(state: DialogueState, now: datetime) -> bool`, `parse_answer(text: str, state: DialogueState | None, *, now: datetime) -> DialogueAnswer | None`. Amplía `Intent.action` con `mention_product`; ninguna nueva acción de escritura del modelo.

**Helpers de tests:** `Clock(now: datetime)` callable con `advance(seconds: int) -> None`; `make_repo(tmp_path: Path) -> Repository`; `seed_line(repo: Repository, description: str, quantity: int | None = None) -> ListLine` mediante inbox/apply_intent reales; `send(repo, text, interpreter=None, *, clock=None, update_id=None, user_id=7) -> Reply` mediante Conversation real; `order_count(repo) -> int`. El clock debe llegar al constructor Conversation cuando Task 3 lo añada; antes no usar send con clock. No mocks de SQLite.

- [ ] **Step 1 — RED:** tests con nombres/asserts siguientes; construir estados completos mediante fixture de tests con `now=datetime(2026,10,1,12,tzinfo=UTC)`:

```python
def test_expiry_boundary_and_canonical_product_names(state):
    assert expired(state, state.updated_at + timedelta(seconds=899)) is False
    assert expired(state, state.updated_at + timedelta(seconds=900)) is True
    assert canonical_name("  ARRÓZ   integral ") == "arroz integral"
    assert canonical_name("arroz") != canonical_name("arroz integral")

def test_answers_require_one_live_question(duplicate_state, replace_state):
    assert parse_answer("sí", duplicate_state, now=duplicate_state.updated_at) is None
    assert parse_answer("sí", replace_state, now=replace_state.updated_at).kind == "confirm"
    assert parse_answer("añádelo", None, now=replace_state.updated_at) is None
    assert parse_answer("sí", replace_state, now=replace_state.expires_at) is None
```

Añadir `test_answer_never_authorizes_purchase_or_unsupported_units`: `/comprar`, `compra la lista`, «2 kg», «0», «-2», «2.5» no producen respuesta contextual. `test_contract_rejects_model_control_fields`: `Intent(action='mention_product', duplicate_confirmed=True)` falla por extra; `DialogueDecision` rechaza mutation+legacy simultáneos. `test_quantity_and_selection_are_question_specific`: bare 2 en quantity produce quantity; en select_line produce select; fuera de pregunta no produce cambio.

- [ ] **Step 2 — verificar RED:** `.venv\Scripts\python.exe -m pytest tests/test_dialogue.py -q` → FAIL por módulo/contratos ausentes; ninguna red/modelo.
- [ ] **Step 3 — implementar:** firmas/contratos indicados, validadores de exclusión y vocabulario cerrado de respuestas (`añádelo`, `añádelo a mi lista`, `añade eso`, `añadir otra línea`, `cambiar cantidad`, `sustitúyelo`, `confirmo`, `sí`, `conserva la cantidad`, `cancelar`, `no`, números y unidades soportadas), normalizado y whole-message. Cada forma exige pregunta/opciones compatibles; no substring matching.
- [ ] **Step 4 — GREEN:** comando de Step 2 y `.venv\Scripts\python.exe -m ruff check dialogue.py domain.py tests/dialogue_support.py tests/test_dialogue.py` → PASS. Ejecutar suite completa → PASS.
- [ ] **Step 5 — commit:** `git add dialogue.py domain.py pyproject.toml tests/dialogue_support.py tests/test_dialogue.py`; `git commit -m "feat: define bounded dialogue state and scoped answers"` → commit local creado.

### Task 2: Estado duradero y migración v6

**Files:** crear `migrations/006.sql`, `dialogue_storage.py`, `tests/test_dialogue_storage.py`; modificar `storage.py:Repository/migrate/assert_authorized_owner`, `pyproject.toml:py-modules`, `tests/test_product_memory.py` y `tests/test_storage.py` donde comprueban versión actual.

**Interfaces:** consume contratos Task 1 y `_connection(write=...)`. Produce mixin `DialogueRepository`, `dialogue_state(self, user_id: int, chat_id: int, *, now: datetime) -> DialogueState | None`, `_read_dialogue_state(db: sqlite3.Connection, user_id: int, chat_id: int) -> DialogueState | None`, `_write_dialogue_state(db: sqlite3.Connection, state: DialogueState | None, user_id: int, chat_id: int) -> None`. Integración `class Repository(CheckoutRepository, DialogueRepository)`; no aplicación de lista nueva todavía.

- [ ] **Step 1 — RED:** `test_v5_upgrade_preserves_list_orders_offset_and_observations`: crear DB v5 real, una lista/orden fake y offset42; migrar dos veces; `PRAGMA user_version == 6`, snapshots/lista/offset42/four observations iguales. `test_legacy_undated_clarifications_do_not_grant_fresh_permissions`: insertar clarify de quantity/remove en v5; después de upgrade tabla legacy vacía y `dialogue_state(...) is None`; lista unchanged. `test_state_roundtrip_owner_and_read_does_not_renew`: escribir estado en una transacción de test, reabrir, comprobar igualdad, otro user/chat devuelve None, leer a+899 no cambia `updated_at/expires_at`, a+900 devuelve None. `test_foreign_state_blocks_owner_assertion`: estado con user/chat ajenos hace fallar assert_authorized_owner incluso sin inbox ajeno.

```python
def test_state_roundtrip_owner_and_read_does_not_renew(repo, state):
    # Fixture ingests state.focus.source_update_id for the same user/chat first.
    with repo._connection(write=True) as db:
        repo._write_dialogue_state(db, state, state.user_id, state.chat_id)
    reopened = Repository(repo.path)
    assert reopened.dialogue_state(7, 7, now=state.updated_at + timedelta(seconds=899)) == state
    assert reopened.dialogue_state(8, 8, now=state.updated_at) is None
    assert reopened.dialogue_state(7, 7, now=state.updated_at + timedelta(seconds=900)) is None
    with reopened._connection() as db:
        assert reopened._read_dialogue_state(db, 7, 7) == state
```
- [ ] **Step 2 — verificar RED:** `.venv\Scripts\python.exe -m pytest tests/test_dialogue_storage.py -q` → FAIL por versión 5/métodos ausentes.
- [ ] **Step 3 — implementar:** v6 crea `dialogue_state(user_id INTEGER, chat_id INTEGER, state_json TEXT NOT NULL, PRIMARY KEY(user_id,chat_id))`; elimina filas de clarifications anteriores sin tocar listas/órdenes. Mantener tabla legacy por compatibilidad temporal. Guard de esquema futuro >6. Lectura valida JSON estricto, identidad de clave, fechas y origen del foco en inbox del mismo usuario/chat; corrupción falla cerrado, sin devolver permisos parcialmente válidos. `_write` valida origen antes de insertar. Lectura pública filtra caducidad sin escritura. Actualizar comprobaciones de versión solo tras observar el fallo previsto de tests actuales.
- [ ] **Step 4 — GREEN:** comando de Step 2, `.venv\Scripts\python.exe -m pytest tests/test_storage.py tests/test_product_memory.py tests/test_runtime.py -q` y Ruff de módulos tocados → PASS. Suite completa → PASS.
- [ ] **Step 5 — commit:** añadir solo archivos de Task 2; `git commit -m "feat: persist expiring dialogue state without resetting user data"` → commit local creado.

### Task 3: Altas contextuales, duplicados, cantidades y respuestas

**Files:** crear `dialogue_controller.py`, `dialogue_replies.py`, `tests/test_dialogue_conversation.py`; modificar `dialogue_storage.py`, `conversation.py`, `storage.py:apply_intent/pending_clarification`, `pyproject.toml`, `tests/test_conversation.py`, `tests/test_product_queries.py`, `tests/test_runtime.py` y helpers solo donde cambia el contrato documentado.

**Interfaces:** consume Tasks 1/2. Produce `reduce_dialogue(message: IncomingMessage, proposal: Intent | None, state: DialogueState | None, lines: list[ListLine], reserved_ids: frozenset[str], *, now: datetime) -> DialogueDecision`; `render_dialogue_result(decision: DialogueDecision, affected: ListLine | None, lines: list[ListLine], legacy_reply: Reply | None = None) -> Reply`; `DialogueRepository.apply_dialogue(update_id: int, proposal: Intent | None, mode: str, *, now: datetime) -> Reply`; `Conversation(repo, interpreter, *, clock: Callable[[], datetime] | None = None)` conserva llamadas actuales. Model route futura: detectar opcionalmente `parse_with_dialogue(text, lines, products, state)`; fallback a parse_with_context o parse sin mandar a otro proveedor.

- [ ] **Step 1 — RED:** tests de Conversation/Repository reales:

```python
def test_capture_flow_remembers_product_without_literal_pronouns(repo, clock):
    send(repo, "necesito arroz por favor", add_proposal("arroz"), clock=clock)
    send(repo, "2", clock=clock)
    reply = send(repo, "ahora arroz integral", mention_proposal("arroz integral"), clock=clock)
    assert "añadir" in reply.text.lower() and "sustituir" in reply.text.lower()
    assert len(repo.list_lines()) == 1
    send(repo, "añádelo a mi lista", clock=clock)
    send(repo, "2 paquetes", clock=clock)
    assert [(l.description, l.quantity) for l in repo.list_lines()] == [("arroz", 2), ("arroz integral", 2)]
    assert order_count(repo) == 0
```

`add_proposal/mention_proposal` son FakeInterpreter con Intent exacto, definidos en tests/dialogue_support.py, no producción.

Añadir `test_new_line_not_old_missing_line_receives_quantity`: semilla arroz sin cantidad, añadir pasta, 2 afecta pasta y no arroz. `test_duplicate_requires_choice_for_natural_and_slash_add`: arroz1 → petición arroz,/anadir arroz no cambia hasta elegir, cambiar cantidad+2 fija2/no3; duplicar explícito crea otra línea. `test_same_product_id_different_qualifier_not_duplicate`: pañales Dodot talla3 vs talla4 y pienso vs pienso pollo sin merge. `test_contextual_alias_never_adds_pronoun`: «añade eso» con/sin foco; nunca existe descripción eso/añádelo. `test_model_cannot_invent_focus_or_write_from_question`: propuesta add/mention con descripción no conservada, URL/ID/cantidad inventados, negación/condición/cita o pregunta no crean foco ni línea. `test_cancel_expired_and_unrelated_topic_do_not_apply_old_quantity`: cancel/restart/899/900s, consulta de otro producto y bare2 no alteran antiguo target. `test_options_and_quantity_numbers_cannot_cross`: selección numerada vs cantidad + candidato editado exige aclaración. `test_natural_replies_hide_ids_but_slash_list_keeps_them`: alta/cantidad/lista natural sin UUID; /lista con IDs. `test_diapers_still_need_explicit_packs`: bare2 no cambia, 2 paquetes sí.

- [ ] **Step 2 — verificar RED:** `.venv\Scripts\python.exe -m pytest tests/test_dialogue_conversation.py -q` → FAIL por controller/clock/context route/comportamiento ausentes.
- [ ] **Step 3 — implementar controlador/respuestas:** reducer revalida texto/propuesta y foco contra filas sin I/O. Extraer/reutilizar las comprobaciones de producto/negación/variantes actuales para no mantener dos gramáticas divergentes. Textos `ahora X` y propuestas mention solo identifican producto íntegro; cantidades/IDs/URL/question en una propuesta mention se rechazan. El modelo no puede preparar una sustitución confirmada. Tras cambiar tema eliminar permisos previos; formular preguntas por producto concreto sin /comprar. Cancelar no deshace alta ya guardada. Para sustitución de Task 4, ofrecer opción y conservar propuesta sin escribir todavía.

No confundir números de talla/tipo/etapa con cantidad: aceptar únicamente esos calificadores numéricos explícitos si se conservan completos en la descripción, sin interpretarlos como envases. Añadir `test_numeric_product_qualifier_is_preserved_not_quantity` con `necesito Dodot talla 4`/`Blemil etapa 2` completos → quantityNone y product_idNone; si el modelo los omite, no hay alta/foco. Otras expresiones numéricas ambiguas mantienen aclaración/comando explícito, sin inventar kg/l ni empaquetado.
- [ ] **Step 4 — implementar aplicación/integración:** `apply_dialogue` abre una sola transacción, recarga mensaje/estado/filas/reservas, ejecuta reducer, aplica mutación permitida y vincula estado a fila/revisión real; construye reply e inbox/outbox atómicos. No aceptar decisiones arbitrarias en una API pública: solo propuestas sin autoridad; recalcular decisión dentro de transacción. `apply_intent(conversation=True)` delega al flujo nuevo; `conversation=False` conserva el camino interno de tests/checkout. `pending_clarification(user_id)` adapta pregunta quantity/remove_id vigente para compatibilidad, no revive filas legacy. Conversation no interpreta respuestas mediante su rama legacy antes del controlador. Comandos slash/compra se reparsan del inbox, no del intent del modelo; buy incompleto conserva aclaración sin autoorden. Modelo stopped no bloquea respuestas cerradas. No llamar HTTP dentro de la transacción.
- [ ] **Step 5 — GREEN:** comando de Step 2 y `.venv\Scripts\python.exe -m pytest tests/test_conversation.py tests/test_product_queries.py tests/test_runtime.py tests/test_dialogue_storage.py -q` → PASS; ajustar solo expectativas del nuevo UX/duplicados, conservar todas las assertions de seguridad y compras. Suite completa y `.venv\Scripts\python.exe -m ruff check .` → PASS.
- [ ] **Step 6 — commit:** añadir solo archivos de Task 3; `git commit -m "feat: keep shopping dialogue focused across additions and quantities"` → commit local creado.

### Task 4: Sustitución confirmada y protección transaccional

**Files:** modificar `dialogue_controller.py`, `dialogue_replies.py`, `dialogue_storage.py`; crear `tests/test_dialogue_replacement.py`. No modificar lógica de checkout/recovery.

**Interfaces:** amplía comportamiento del reducer/apply_dialogue/render ya definidos; no nueva firma ni acción del modelo. `DialogueMutation(kind='replace', target=LineRef(...), description=..., quantity=...)` solo se genera desde confirmaciones validadas del estado.

- [ ] **Step 1 — RED:** `test_replace_requires_origin_destination_confirmation_and_quantity`: arroz2 → ahora integral → sustituir → sí → sin cambios hasta conservar2/indicar3; mismo ID, nueva descripción, revision+1, cantidad elegida; cero órdenes. `test_replace_missing_quantity_does_not_delete_origin`: origen quantityNone, confirmar sigue sin cambio hasta respuesta válida. `test_duplicate_destination_requires_separate_lines_confirmation`: existente arrozintegral4 no se fusiona/suma; rechazo/cancel deja todo igual; confirmar líneas separadas sustituye origen preservando cantidad elegida y mantiene destino4. `test_replacement_rejects_stale_missing_or_reserved_origin`: editar/quitar/reservar tras propuesta; confirmación no sustituye ni desreserva; informar/reabrir decisión. Reserva se crea con Repo/orden de test, nunca bot/tienda. `test_restricted_replacement_preserves_full_description`: Blemil etapa2/pienso pollo no se vuelven fórmula permitida/pienso pescado; resolve_product actual determina product_idNone.

Añadir `test_replace_outbox_failure_rolls_back_and_retry_changes_once`: trigger SQLite que aborta INSERT outbox; antes/después iguales para fila/state/inbox; retirar trigger → una revisión incrementada; replay devuelve mismo Reply y TTL idéntico. `test_prior_order_snapshot_immutable_after_allowed_replace`: snapshot de orden de test existente permanece igual al sustituir línea no reservada; no tocar ningún mecanismo externo. `test_model_replace_or_set_quantity_cannot_confirm_pending_proposal`: Intent remove/set_quantity/buy, IDs fabricados o «sí» condicional no cruzan confirmaciones. `test_cancel_at_every_replace_step_preserves_original`: parametrizar preguntas de destino/origen/cantidad/conflicto.

```python
def test_replace_requires_origin_destination_confirmation_and_quantity(repo, clock):
    original = seed_line(repo, "arroz", 2)
    send(repo, "necesito arroz", add_proposal("arroz"), clock=clock)
    # Resolve the duplicate dialogue explicitly, establishing focus on original.
    send(repo, "cambiar cantidad", clock=clock)
    send(repo, "2", clock=clock)
    original = repo.list_lines()[0]
    send(repo, "ahora arroz integral", mention_proposal("arroz integral"), clock=clock)
    send(repo, "sustitúyelo", clock=clock)
    assert repo.list_lines() == [original]
    send(repo, "sí", clock=clock)
    assert repo.list_lines() == [original]
    send(repo, "conserva la cantidad", clock=clock)
    changed = repo.list_lines()[0]
    assert (changed.id, changed.description, changed.quantity, changed.revision) == (
        original.id, "arroz integral", 2, original.revision + 1,
    )
    assert order_count(repo) == 0
```

- [ ] **Step 2 — verificar RED:** `.venv\Scripts\python.exe -m pytest tests/test_dialogue_replacement.py -q` → FAIL porque sustitución no implementada/no llega a estado final.
- [ ] **Step 3 — implementar:** origen seleccionado por foco vigente o candidatos explícitos; sí confirma únicamente origen/destino ya planteados. Resolver cantidad y duplicado sin cambios intermedios. Recheck final target ID/revision, reserva, destino y pruebas de confirmación en misma transacción; `UPDATE list_lines ... revision=revision+1 WHERE id=? AND revision=?`, exigir una fila afectada. Recalcular product_id, conservar ID y source_update_id original de la línea, no modificar snapshots/order_lines. Rebind foco/revisión después del UPDATE. Preguntas y cancelaciones jamás llevan una mutación replace parcial.
- [ ] **Step 4 — GREEN:** comando de Step 2 y `.venv\Scripts\python.exe -m pytest tests/test_dialogue_conversation.py tests/test_dialogue_storage.py tests/test_checkout.py tests/test_recovery.py -q` → PASS. Suite completa y Ruff → PASS.
- [ ] **Step 5 — commit:** añadir solo archivos de Task 4; `git commit -m "feat: confirm atomic product replacements without rewriting orders"` → commit local creado.

### Task 5: Gemma recibe contexto de diálogo sin autoridad

**Files:** modificar `ollama_interpreter.py`, `tests/test_ollama_interpreter.py`, `tests/test_dialogue_conversation.py` si falta cobertura del dispatch. La detección opcional en Conversation ya pertenece a Task 3.

**Interfaces:** `OllamaInterpreter.parse_with_dialogue(text: str, lines: list[ListLine], products: list[ObservedProduct], state: DialogueState | None) -> Intent` async. `parse` y `parse_with_context` conservan firmas/compatibilidad; delegan a un emisor privado común. El estado recibido está filtrado por caducidad en Conversation y los campos enviados se reducen aún más.

- [ ] **Step 1 — RED:** `test_dialogue_payload_bounded_and_no_history_or_control_flags`: MockTransport captura cuerpo real; conserva límite20 líneas/5 fichas y strings160 chars; incluye foco description/question/options y descripciones actuales de candidatos (máximo5), nunca ID/revision, flags confirmed, timestamps, source_update_id, configuración ni transcript. `test_mention_product_is_proposal_not_mutation`: JSON action mention_product válido devuelto, Conversation mantiene lista hasta respuesta. `test_answers_and_slash_commands_skip_ollama`: intérprete que falla si se invoca para preguntaquantity/select/confirm vigente y comandos. `test_model_destructive_action_with_live_focus_is_rejected`: salida set_quantity/remove/buy jamás aplica. `test_timeout_invalid_json_and_redirect_preserve_dialogue`: mismo estado/lista/backlog, no fallback. `test_truncated_context_cannot_grant_confirmation`: >5 candidatos o descripción truncada no convierten selección incompleta en permiso; referencia ambigua pide aclaración en controlador con snapshot completo.

El objeto JSON adicional tiene exactamente claves `focus`, `question`, `options`, `candidates`; `focus` es descripción o null, candidates son descripciones (no IDs) de filas del snapshot. Se ubica en `context['dialogue']`; con stateNone se envía null, manteniendo las rutas antiguas.

```python
def test_dialogue_payload_bounded_and_no_history_or_control_flags(captured_body):
    context = json.loads(captured_body["messages"][1]["content"])
    assert captured_body["options"]["num_ctx"] == 4096
    assert len(context["lines"]) <= 20 and len(context["products"]) <= 5
    assert set(context["dialogue"]) == {"focus", "question", "options", "candidates"}
    assert len(context["dialogue"]["candidates"]) <= 5
    assert all(isinstance(name, str) and len(name) <= 160 for name in context["dialogue"]["candidates"])
```

Fixture captured_body debe ejecutar parse_with_dialogue real con MockTransport y estado de test; no construir el payload esperado mediante el serializador de producción.
- [ ] **Step 2 — verificar RED:** `.venv\Scripts\python.exe -m pytest tests/test_ollama_interpreter.py tests/test_dialogue_conversation.py -q` → FAIL por parse_with_dialogue/contexto ausentes.
- [ ] **Step 3 — implementar:** instrucciones específicas de shopping, mención sin alta, preservar marca/variante y qtyNone; reglas de prioridad sin prometer obediencia del modelo. Contexto es dato no fiable; serialización del estado explícita, no model_dump indiscriminado. Mantener URL `http://127.0.0.1:11434/api/chat`, contexto4096, thinkFalse, timeout total60s, sin proxies/redirecciones/logs/herramientas. El controlador resuelve respuestas cerradas sin HTTP, incluso si Ollama está caído. No habilitar proveedor ni tocar configuración privada.
- [ ] **Step 4 — GREEN:** comando de Step 2, suite completa y Ruff → PASS. Revisar compatibilidad de fakes/OpenAI que solo exponen parse; no añadir fallback ni modificar proveedor OpenAI.
- [ ] **Step 5 — commit:** añadir solo archivos de Task 5; `git commit -m "feat: provide bounded dialogue context to local Gemma"` → commit local creado.

### Task 6: Integración, prueba local y entrega sin activar bot

**Files:** crear `tests/test_dialogue_end_to_end.py`, `scripts/Probe-Dialogue.ps1`; modificar `docs/setup.md`, `docs/superpowers/progress.md`; añadir informe versionado `docs/superpowers/prueba-dialogo-contextual-2026-10-01.md`. Helpers adicionales solo en tests/dialogue_support.py.

**Interfaces:** consume Conversation/Repository/clock/model de Tasks 1–5, TelegramIO/FakeBot y runtime actuales. Probe opt-in usa root temporal bajo `$env:LOCALAPPDATA\Temp\opencode`, datos inventados y Ollama existente; nunca load_settings/configure/doctor del bot privado.

- [ ] **Step 1 — RED:** `test_dialogue_survives_runtime_restart_and_outbox_replay`: FakeBot+TelegramIO reales, DB temporal y Conversation real; ejecutar captura íntegra y reemplazo, reiniciar en pregunta pendiente, reprocesar confirmación, entregar outbox; nombres/cantidades correctos, cero órdenes y ninguna llamada de checkout/store. `test_expired_restart_does_not_consume_number_as_selection`: reloj+900, bare2 no altera fila ni TTL; nueva petición explícita continúa. `test_model_failure_keeps_commands_and_contextual_answers_available`: fallo del intérprete para una frase libre, /lista y respuesta cerrada vigente siguen útiles, no mutación de fallo ni fallback. `test_foreign_chat_never_consumes_owner_context`: update ajeno no entregado a conversación, no cambio de estado/lista/notices propios.

```python
def test_expired_restart_does_not_consume_number_as_selection(repo, clock):
    send(repo, "necesito arroz", add_proposal("arroz"), clock=clock)
    before = repo.list_lines()
    clock.advance(seconds=900)
    reopened = Repository(repo.path)
    send(reopened, "2", clock=clock)
    assert reopened.list_lines() == before
    assert reopened.dialogue_state(7, 7, now=clock()) is None
    assert order_count(reopened) == 0
```
- [ ] **Step 2 — verificar RED:** `.venv\Scripts\python.exe -m pytest tests/test_dialogue_end_to_end.py -q` → comprobar el fallo del escenario aún no cubierto; si todas las rutas ya pasan, registrar esa evidencia como integración verde de funcionalidades anteriores, no inventar un RED ni cambiar producción para provocarlo.
- [ ] **Step 3 — ajustar integración mínima solo ante defecto reproducido:** usar systematic-debugging y su regresión RED→GREEN; ningún cambio de checkout/tiendas. Mantener un único worker del test, no arrancar runtime con Settings privadas.
- [ ] **Step 4 — comprobar Ollama voluntariamente:** script explícito sin descarga, install ni efectos al importar; secuencias independientes de alta/cantidad/mención/pronombre, duplicado/sustitución/cantidad, consulta intermedia/cancelación y adversarios. Grabar solo resultados inventados en informe, no mensajes privados; verificar assertions de estado/0órdenes; medir primera respuesta y calientes, `/api/ps` inicial sin descargar modelo ni parar otro proceso. Script devuelve no-cero si alguna expectativa falla y limpia su DB con conexiones cerradas. Ejecutar `powershell.exe -NoProfile -File scripts/Probe-Dialogue.ps1` → reportar evidencia real PASS o FALLÓ, no sustituirla por fakes; si no hay servicio, pendiente sin activación.
- [ ] **Step 5 — documentación:** manual con ejemplos del diálogo, caducidad15min, cancelación sin undo, duplicados/confirmación/total y límites de envases/pañales. Separar tests offline, prueba aislada y Telegram privado no probado por esta fase. Conservar receta worktree `-P`/PYTHONPATH y protección ACL existente. No recomendar /comprar para aceptación. Si Gemma sigue fallando, dejar esa limitación explícita; no cambiar configuración para que el usuario lo pruebe por inferencia.
- [ ] **Step 6 — verificación:** `.venv\Scripts\python.exe -m pytest -q` → PASS; `.venv\Scripts\python.exe -m ruff check .` → All checks passed; `git diff --check` → limpio. Anotar resultados finales tras cualquier fix en el ledger y docs.
- [ ] **Step 7 — commit:** añadir solo archivos de Task 6; `git commit -m "test: verify contextual shopping dialogues across restart and replay"` → commit local creado.

## Revisión final y handoff de ejecución

Revisión independiente de todo el rango desde la base con spec/plan, cinco Review Focus y decisiones del ledger. Hallazgos Critical/Important se reparan con regresiones RED→GREEN y suite completa; menores se documentan. No subir, fusionar, parar/reiniciar bot ni abrir configuración privada.

Dependencias: 1→2→3→4; 3→5; 4+5→6. Interfaces compartidas deliberadas y serializadas; no paralelizar tareas que editan Conversation/storage/controller. La elección de ejecución queda pendiente de revisión del plan por el usuario.

## Autoevaluación del plan

- Spec §§1–5: Tasks1/2/3/5 (estado, autoridad, TTL, context routing).
- Spec §§6–8: Tasks3/4 (duplicados, producto concreto, cantidades, sustitución, UX).
- Spec §9: Tasks2/3/4/5 (migración, aislamiento, transacción, replay, restricciones).
- Spec §§10–11: Task6, revisión final y gate de aprobación; sin aceptación privada implícita.
- Review Focus1→Task3; 2→Tasks3/4/6; 3→Tasks3/4; 4→Tasks2/4/6; 5→Tasks3/5/6.
- No dependencia/API indefinida ni función de producción usada solo por tests. No nueva dependencia, columna de cantidades ni modificación de snapshots. Los tests de versión se actualizan por la migración real, no para esconder fallos.
