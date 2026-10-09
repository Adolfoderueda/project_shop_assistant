# Preguntas guiadas en Telegram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incorporar preguntas duraderas con botones opcionales y respuestas libres acotadas, sin perder el borrador ni guardar antes de una confirmación final válida.

**Architecture:** Un controlador puro decide preguntas, alcance y transiciones sobre el estado real. SQLite conserva eventos tipados, propuestas con procedencia, opciones consumibles y testigos de entrega; Telegram solo autentica y transporta. E4B devuelve sugerencias acotadas, nunca ejecuta directamente el guardado ni interpreta tokens de botones.

**Tech Stack:** Python 3.12+, SQLite, Pydantic 2, httpx, python-telegram-bot >=22.5,<23, pytest y Ruff existentes; Ollama local con gemma4:e4b-it-q4_K_M. Sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-10-09-preguntas-guiadas-telegram-design.md`, aprobada por el usuario después de `ed01d8e`.

## Global Constraints

- Botones solo cuando falten datos/selección; respuesta libre disponible, no formulario obligatorio desde el primer mensaje.
- La aplicación controla identidad, estado, preguntas, botones, resultados y escritura.
- Una selección de grupo o producto no guarda líneas; la confirmación final es separada y vinculada al resumen completo vigente.
- Un agente local; sin framework multiagente ni instalación de OpenCode.
- Siguiente migración v10 sobre la base v9, transaccional y con rollback de migración fallida.
- El límite sigue siendo 20 elementos por propuesta; no truncar elementos ni resúmenes.
- Tokens: `q:` más 22 caracteres base64url de 128 bits aleatorios; 24 bytes ASCII.
- Historial autorizado: los últimos tres pares usuario/respuesta completados de esa conversación, más pregunta y estado actuales.
- 24.000 bytes de mensajes+schemas, cuatro llamadas al modelo, ocho herramientas por turno, temperatura 0, `think=False`, contexto 8192 y salida 512.
- La pregunta caduca a más tardar con el borrador; no renovar por una consulta ni por pulsar un botón antiguo.
- Revisión final en un mensaje, dentro del límite de aplicación y de 4.000 unidades UTF-16 conservadoras; si excede, dividir la petición, nunca habilitar revisión truncada.
- Cantidades desconocidas no son cero; no sumar duplicados automáticamente, elegir filas actuales no reservadas y revisar base+adicional=total.
- Mantener textos originales y aportaciones; no crear mensajes sintéticos para ejecutar parsers legacy.
- No copiar los prototipos temporales ni relajar su filtro literal como solución. Alcance candidato no es alcance autorizado.
- `guided_questions=False` por defecto, solo válido con `skills_agent`; el rollback usa código nuevo con flag apagado, no downgrade de schema.
- Sin cambios privados, compras nuevas, modelos nuevos, activación, reinicio, merge o push durante ejecución del plan.
- Cualquier futura prueba Telegram necesita autorización separada, base vacía aislada y bloqueo explícito de buy/resume/checkout; `dry_run` no basta.
- Mantener abierta la aceptación Task 7 anterior; resolver sus fallos de consulta y duplicados internos, no eximirlos por este diseño.

## Review Focus

- «No» al tema adicional conserva el borrador principal; un «sí» a una selección nunca confirma la lista. Pruebas en tareas 2, 4 y 7.
- Duplicado de envío incierto: un mensaje sin entrega registrada no concede autoridad; una copia conocida sigue siendo consumible una sola vez. Pruebas en tareas 4 y 5.
- Una corrección explícita de un producto ya completado no se pierde porque la pregunta actual solo enumere cantidades ausentes. Pruebas en tareas 2 y 6.
- Producto llamado «sí», «todos» o como una etiqueta de botón no cambia el significado de controles ni autoriza una opción de otra pregunta. Pruebas en tareas 1, 2 y 6.
- Nueva petición que supera 20 elementos o se mezcla con condiciones/duplicados conserva toda la procedencia anterior, sin reemplazar silenciosamente el lote. Pruebas en tareas 2 y 4.

---

## Autorización, workspace y ejecución

Este documento prepara la ejecución, no la inicia. Requiere revisión humana del plan y selección de método. La aprobación histórica de subagentes para el agente anterior no sustituye esa decisión para este plan.

Al comenzar ejecución, cargar using-git-worktrees y verificar aislamiento. El worktree actual contiene el código que lee el worker experimental en marcha: NO editarlo mientras ese worker siga activo. Crear un worktree hijo desde el commit documental aprobado para implementar, sin limpiar ni sustituir el worktree anterior; no mover bases/settings privadas. Considerar session_move para hacer el nuevo worktree la ubicación de ejecución.

Antes de cada tarea: comprobar cambios existentes, leer spec y ledger, RED→GREEN, revisión de la tarea y commit selectivo. No redispatch de tareas 1–6 del plan anterior. Si un contrato vecino debe cambiar, actualizar este plan y los consumidores antes de continuar; no inventar APIs en paralelo.

## Mapa de archivos e interfaces comunes

| Archivo | Responsabilidad |
| --- | --- |
| `domain.py` | Evento callback y unión de entradas; teclado opcional serializable en Reply |
| `shopping_agent/guided_contracts.py` | Pregunta, tema, aportaciones v2, estado, respuesta candidata y decisión pura |
| `shopping_agent/guided_controller.py` | Reducir preguntas/selecciones y planificar la siguiente pregunta |
| `shopping_agent/guided_replies.py` | Preguntas, teclados lógicos y revisión íntegra, sin texto libre del modelo |
| `shopping_agent/guided_storage.py` | Transacciones de estado guiado, tokens, replays y testigos |
| `shopping_agent/guided_ollama.py` | Native-tool interpretación acotada que devuelve datos, no efectos |
| `shopping_agent/guided_conversation.py` | Orden de controles, legacy, modelo y commit guiado |
| `storage.py`, `presentation_storage.py`, `shopping_agent/storage.py` | Adaptación estrecha de eventos/outbox/procedencia y composición del repositorio |
| `migrations/010.sql` | Schema duradero aditivo y versión 10 |
| `telegram_io.py` | Autenticación, callbacks, envíos con teclado, recibos y acuses |
| `runtime.py`, `config.py`, `cli.py` | Enrutamiento y flag experimental con revocación segura |
| `scripts/probe_guided_questions.py` | Aceptación sintética offline y con E4B real; sin configuración privada |
| `tests/test_guided_*.py`, `tests/guided_helpers.py` | Oráculos de estado, fixtures sintéticos y transporte externo sustituido |

Nuevos módulos dentro de `shopping_agent` no requieren declarar otro paquete. Verificar inclusión de `migrations/010.sql` junto con migraciones anteriores en el mecanismo de distribución; no instalar build tools sin autorización. Si no puede verificarse el wheel, registrarlo como bloqueo, no declarar distribución verificada.

### Tipos compartidos que fija la tarea 1

- `IncomingMessage` mantiene sus cuatro campos y JSON histórico. `IncomingCallback` añade `kind: Literal['callback']='callback'`, `update_id`, `user_id`, `chat_id`, `callback_query_id`, `message_id`, `bot_id`, `data`; todos proceden de transporte autenticado. `IncomingEvent = IncomingMessage | IncomingCallback`; decode_event acepta JSON histórico de mensaje sin kind y callback con kind explícito, nunca decide por texto vacío.
- `InlineButton(label: str, token: str)` y `InlineKeyboard(rows: tuple[tuple[InlineButton, ...], ...])`; `Reply.keyboard: InlineKeyboard | None = None`, conservando `text` y `order_id`.
- `GuidedProposal(AgentProposal)`: `schema_version=2`, `contributions: tuple[Contribution,...]`, `review: ReviewWitness | None`. `Contribution(update_id, positions, kind)` usa `kind=create|edit|append|decision`; no identidad del modelo. `StoredProposal = AgentProposal | GuidedProposal`, discriminado por schema_version.
- `ReviewWitness(proposal_id, revision, question_id, summary_digest, source_update_id, notice_id, delivered_message_id: int | None)`; entrega pendiente no es autoridad de guardar.
- `QuestionKind = scope|quantity_shared|quantity_single|unit|duplicate|source_line|condition|topic|review`; `QuestionStatus = active|consumed|expired|revoked`.
- `Choice(kind, label: str, positions=(), candidate_index=None, unit=None)` con `kind=one_each|same_quantity|different_quantities|write_answer|choose_scope|choose_unit|separate|set_total|choose_line|remove_condition|append_topic|keep_topic|confirm|correct|cancel`. Label lo genera la aplicación; validar combinaciones: solo datos del tipo de opción, posiciones únicas ofrecidas.
- `GuidedQuestion(id, version, owner_id, chat_id, kind, proposal_id, proposal_revision, positions, choices, source_update_id, created_at, expires_at, status, text, candidate: QuantityCandidate | None)`; candidatos no se aplican al guardar la pregunta.
- `PendingTopic(id, version, source_update_id, original_text, items, condition, proposal_id, proposal_revision, expires_at)`; condiciones se conservan, no se dan por verificadas.
- `GuidedState(snapshot: AgentSnapshot, question: GuidedQuestion | None, topic: PendingTopic | None, review: ReviewWitness | None)`; snapshot.proposal y ProposalDecision.proposal aceptan StoredProposal sin invalidar v1.
- `QuantityCandidate(kind='quantity', patches: tuple[ItemPatch,...], source_update_id: int)`; `ScopeCandidate(kind='scope', positions, source_update_id)`; `TopicCandidate(kind='topic', adds: ProposeAdds, source_update_id)`; `ChangeCandidate(kind='change', change: ProposeChange, source_update_id)`; `ReadCandidate(kind=list|fiche, query=None)`; `ControlCandidate(kind=cancel|clarify)`. Kinds son Literals estrictos; source_update_id lo estampa la aplicación después de leer el resultado, no es argumento nativo permitido al modelo.
- `GuidedAnswer` es esa unión discriminada, sin confirm/save. `ResolvedChoice(question_id, question_version, choice_index, source_update_id)` solo lo crea la aplicación tras validar evento/opción.
- `GuidedDecision(state: GuidedState, reply: Reply, mutations: tuple[DialogueMutation,...]=(), reason: str)`; mutaciones solo con `reason=confirmed` y testigo vigente. `GuidedModelResult(answer: GuidedAnswer | None, reason: str, model_calls: int, tool_calls: int)` no contiene Reply redactado por el modelo.

Evitar ciclos: Contribution, ReviewWitness, GuidedProposal y StoredProposal se definen junto a AgentProposal en `shopping_agent/contracts.py`; `guided_contracts.py` los importa, no al revés. InlineButton/InlineKeyboard/IncomingCallback se definen en `domain.py`, que no importa los módulos del agente. `guided_contracts.py` define estado/preguntas/candidaturas.

`GuidedState.review` es la proyección del testigo de GuidedProposal, no una segunda autoridad almacenada independientemente; al leer/validar deben coincidir. No habilitar confirmación con delivered_message_id=None. Tarea 4 integra record_delivery para completar el testigo únicamente cuando notice/chat/digest y revisión vigente coincidan en esa misma transacción.

### Tarea 1: Contratos compatibles y autoridad explícita

**Files:** modificar `domain.py`, `shopping_agent/contracts.py`; crear `shopping_agent/guided_contracts.py`, `tests/test_guided_contracts.py`, `tests/guided_helpers.py`.

**Interfaces:** produce los tipos compartidos anteriores y `decode_event(payload: dict) -> IncomingEvent`, `decode_proposal(payload: str) -> StoredProposal`. Helpers de tests: `message(update_id, text, owner=7)`, `callback(update_id, token, query_id='query', message_id=100, owner=7, bot_id=99)`, `state_fixture(*, quantities=(None,None,None), now=NOW, condition=None) -> GuidedState`; NOW fija UTC en tests y nombres huevos/carne/atun. Constante sintética `VALID_TOKEN = 'q:' + 'A' * 22`, solo para tests de formato/ingest, no para conceder opciones; los tokens de estado se obtienen de choice_token en tarea 4. No repositorio ficticio.

- [ ] **1. Escribir tests RED** con JSON v1 literal y v2 inválido. Afirmaciones mínimas:

```python
def test_old_reply_and_message_remain_readable():
    assert Reply.model_validate_json('{"text":"pendiente"}').keyboard is None
    assert decode_event({"update_id": 1, "user_id": 7, "chat_id": 7, "text": "sí"}) == message(1, "sí")

def test_model_answer_cannot_confirm_or_save():
    for payload in ({"kind": "confirm"}, {"kind": "save"}):
        with pytest.raises(ValueError):
            decode_guided_answer(payload)
```

Definir `decode_guided_answer(payload: dict) -> GuidedAnswer` aquí. Añadir tests de bool como posición/cantidad, extra fields, tokens de 24 bytes, orden de filas de teclado, Choice incompatible, pregunta caducada/versión inválida, v1 sin aportaciones v2 y v2 con review incompleto. `test_product_control_words_are_data` conserva nombres sí/todos sin convertirlos en controles.
- [ ] **2. Ejecutar** `python -P -m pytest tests/test_guided_contracts.py -q`; observar fallos por ausencia del nuevo contrato, no por fixtures rotos.
- [ ] **3. Implementar contratos** con Model estricto congelado, límites existentes y unión por versión. Conservar validaciones de cantidades/TTL; v2 exige aportaciones con posiciones existentes y fuente válida. No alterar semántica v1 ni quitar revisiones.
- [ ] **4. Verificar** `python -P -m pytest tests/test_guided_contracts.py tests/test_agent_contracts.py -q`. Correr también `python -P -m pytest -q` y `python -P -m ruff check .`. Esperado: sin regresiones; registrar cualquier fallo por nombre.
- [ ] **5. Commit selectivo:** `feat: define durable guided question contracts`; revisión de compatibilidad JSON y ausencia de permisos en GuidedAnswer antes de tarea 2.

### Tarea 2: Controlador puro, preguntas y preservación del borrador

**Files:** crear `shopping_agent/guided_controller.py`, `shopping_agent/guided_replies.py`, `tests/test_guided_controller.py`, `tests/test_guided_replies.py`; modificar `shopping_agent/proposals.py` solo para compartir validación/recalcular conflictos sin duplicarla.

**Consumes:** tipos/helper de tarea 1; reglas de proposals.py y render de resumen actual.
**Produces:**
- `next_question(state: GuidedState, event: IncomingEvent, *, now: datetime) -> GuidedQuestion | None`.
- `resolve_text_choice(message: IncomingMessage, question: GuidedQuestion) -> ResolvedChoice | None`: igualdad canónica con etiqueta/índice ofrecido o controles propios de la pregunta; no catálogo de frases libres.
- `reduce_guided(state: GuidedState, event: IncomingEvent, answer: GuidedAnswer | ResolvedChoice | None, *, now: datetime) -> GuidedDecision`.
- `append_topic(state: GuidedState, event: IncomingEvent, *, now: datetime) -> GuidedDecision`.
- `render_question(question: GuidedQuestion) -> Reply` con opciones lógicas todavía sin tokens; `render_review(state: GuidedState) -> Reply`; `review_fits(reply: Reply) -> bool`, verificando límite de aplicación y UTF-16.

Identificadores lógicos de pregunta deterministas por evento/propietario/tipo/versión para replay; tokens aleatorios se crean en repositorio, no en el reductor. La decisión transporta choices de question; Reply.keyboard se completa con tokens en tarea 4.

- [ ] **1. Escribir tests RED** de transición con expectativas independientes:

```python
def test_candidate_does_not_grant_unselected_collective_scope():
    state = state_fixture()
    decision = reduce_guided(state, message(2, "Pon uno"),
        QuantityCandidate(patches=(ItemPatch(position=1, quantity=1),), source_update_id=2), now=NOW)
    assert [p.quantity for p in decision.state.snapshot.proposal.items] == [None, None, None]
    assert decision.state.question.kind == "scope"
    assert decision.mutations == ()

def test_keep_topic_does_not_cancel_main_draft():
    # fixture contiene pregunta topic y tema leche, asociado a revisión actual.
    decision = reduce_guided(topic_state_fixture(), message(3, "no"), None, now=NOW)
    assert decision.state.topic is None
    assert [p.description for p in decision.state.snapshot.proposal.items] == ["huevos", "carne", "atun"]
    assert decision.mutations == ()
```

Agregar `topic_state_fixture() -> GuidedState` a helper aquí. Tests separados: one_each, shared seguido de cantidad, individual seguido de cantidad, corrección de elemento ya completo, sí durante alcance vs sí final, edición mixta, condición persistente, unidad de pañales, filas reservadas, base desconocida, conflictos internos para ambos elementos, origen de cada append, negativo a tema y otra petición con tema pendiente. Para 19+2 elementos: assert estado previo íntegro y tema conservado, sin truncar. `test_control_named_product_does_not_shadow_choice` fija significado por QuestionKind, no por descripción.
- [ ] **2. Ejecutar** `python -P -m pytest tests/test_guided_controller.py tests/test_guided_replies.py -q`; comprobar RED.
- [ ] **3. Implementar reducción**: consumir versión por selección, mantener ID/posiciones al append y añadir Contribution; recomputar conflictos y revocar review al editar/abrir tema. Orden de preguntas: condición/origen/duplicado/unidad obligatoria antes de revisión; cantidades se resuelven por foco compartido/individual. Reutilizar revalidación y límites aritméticos existentes.
- [ ] **4. Implementar render**: preguntas concretas sin datos inventados, candidatos sin aplicación, summary íntegro; revisión con caracteres astrales fuera de 4.000 UTF-16 no es confirmable. Añadir tests de 2.001 caracteres astrales, lote de 20 y muestra de incremento base+delta=total.
- [ ] **5. Verificar** tests de tarea 2, tests existentes de proposals/replies y suite completa. Esperado: todas las transiciones son puras y ninguna edición/cantidad produce DialogueMutation de guardado.
- [ ] **6. Commit:** `feat: reduce guided questions without saving drafts`; revisión del estado y oráculos antes de persistir.

### Tarea 3: Inbox/outbox tipados, schema v10 y recibos de transporte

**Files:** crear `migrations/010.sql`, `tests/test_guided_migration.py`, `tests/test_guided_events.py`; modificar `storage.py`, `presentation_storage.py`.

**Consumes:** IncomingEvent, Reply.keyboard y decode_event de tarea 1.
**Produces Repository methods:**
- `ingest_events(events: list[IncomingEvent], next_offset: int) -> None`; `ingest_batch` delega para mensajes.
- `pending_events() -> list[IncomingEvent]`; `pending_messages()` filtra mensajes sin pasar callbacks a legacy.
- `event_result(update_id: int) -> tuple[IncomingEvent, Reply | None]`; mantener `message_result` con rechazo explícito de callback.
- `pending_replies() -> list[tuple[str, int, Reply]]`; conservar `pending_notices()` legacy.
- `record_delivery(notice_id: str, chat_id: int, message_id: int, digest: str) -> None`.
- `known_delivery(notice_id: str, chat_id: int, message_id: int, digest: str) -> bool`.
- Métodos para tarea 5: `pending_callback_acks() -> list[str]`, `mark_callback_ack(query_id: str, *, expired: bool=False) -> None`.

Migración crea tablas `guided_questions`, `guided_topics`, `guided_tokens`, `telegram_deliveries`; agrega `kind TEXT NOT NULL DEFAULT 'message'`, `payload_json`, `callback_query_id`, `callback_ack_state` al inbox, con índice único parcial de query no NULL. Ack es NULL para message y pending/sent/expired para callback, sin columna añadida después de publicar v10. Las tablas de estado guardan JSON validado; tokens guardan owner/chat/question/version/choice_index/notice/consumed_update/result. Conservar PK update y FK de lista/pedidos a inbox. `telegram_deliveries` PK `(notice_id,chat_id,message_id)` y digest. `PRAGMA user_version=10`; migración v10 se ejecuta en una sola transacción, no mezclar executescript que confirme antes del rollback.

- [ ] **1. Escribir tests RED** en bases sintéticas 0 y v9:

```python
def test_migration_preserves_old_unknown_quantity_and_reply(tmp_path):
    repo = seeded_v9_repo(tmp_path)  # helper construye schema9 y filas históricas literales.
    before = historical_rows(repo)
    repo.migrate()
    assert schema_version(repo) == 10
    assert historical_rows(repo) == before

def test_mixed_events_are_ordered_and_callbacks_are_not_messages(tmp_path):
    repo = migrated_repo(tmp_path)
    repo.ingest_events([message(2, "hola"), callback(3, VALID_TOKEN)], 4)
    assert [e.update_id for e in repo.pending_events()] == [2, 3]
    assert [e.update_id for e in repo.pending_messages()] == [2]
```

Definir helpers de tests de migración en ese fichero: historical_rows consulta explícitamente todas las columnas HISTÓRICAS de inbox/outbox/lista/pedidos con el mismo SELECT antes y después, no SELECT * ni snapshot producido por la migración; probar aparte defaults de las columnas nuevas. Tests adicionales: mismo update con distinto payload, mismo query ID distinto update, cursor tras fallo de INSERT, migración interrumpida antes de user_version, v11 rechazado, Reply viejo sin keyboard y varios delivery IDs mismo aviso. Query duplicada idéntica no reaplica; query_id con contenido distinto falla cerrado.
- [ ] **2. Ejecutar** `python -P -m pytest tests/test_guided_migration.py tests/test_guided_events.py -q`; RED por métodos/schema ausentes.
- [ ] **3. Implementar persistencia de eventos** con transacciones cortas y comparación de identidad antes de INSERT OR IGNORE. Ninguna operación de red. Validar digest/owner/delivery y no marcar sent automáticamente hasta terminar entrega real. Guardar/cargar acuses con los métodos definidos: query expirada es terminal solo para acuse, no para evento de negocio; probar reinicio con ack pending.
- [ ] **4. Adaptar owner/provenance checks** a eventos y tablas nuevas. `_read_prepared` rechaza jobs generativos para callback; `_complete_reply` soporta Reply.keyboard sin introducir orden/pedido. `assert_authorized_owner` detecta estado huérfano o foreign en tablas nuevas.
- [ ] **5. Verificar** tareas 1–3, tests existentes de storage/recovery/presentation y suite completa; cero diferencias en filas históricas después de migrar. Verificar distribución de migraciones sin instalar dependencias; anotar bloqueo de wheel si sigue faltando backend.
- [ ] **6. Commit:** `feat: persist typed Telegram events and delivery receipts`; revisión del rollback real de migración, no solo de user_version.

### Tarea 4: Commit guiado, procedencia v2 y consumo único

**Files:** crear `shopping_agent/guided_storage.py`, `tests/test_guided_storage.py`, `tests/test_guided_provenance.py`; modificar `storage.py` composición, `shopping_agent/storage.py` read/write v1/v2 y `tests/guided_helpers.py`.

**Consumes:** tipos/controlador de tareas 1–2 y eventos/recibos de tarea 3.
**Produces Repository methods:**
- `guided_state(update_id: int, *, now: datetime) -> GuidedState`.
- `apply_guided(update_id: int, answer: GuidedAnswer | ResolvedChoice | None, *, expected_question_version: int | None, now: datetime) -> Reply`.
- `apply_guided_callback(update_id: int, *, now: datetime) -> Reply`.
- `guided_history(user_id: int, chat_id: int) -> tuple[dict, ...]`: máximo seis mensajes de tres pares completados, callbacks traducidos desde opción válida.
- `revoke_guided(user_id: int, *, now: datetime) -> None`: preguntas/temas/tokens/revisiones y propuesta guiada no confirmada, no filas guardadas; evita ceder un borrador v2 al reductor legacy. Avisar en CLI de descarte de pendientes al cambiar modo.

`PersistedCase` helper de tests contiene `repo`, `now`, `source_update_id`; `persisted_case(tmp_path, *, quantities=(None,None,None), condition=None) -> PersistedCase` usa inbox y operaciones reales. Métodos helper: `question()`, `choice_token(kind)`, `record_known_delivery(message_id=100)`, `ingest_message(update_id,text)`, `ingest_callback(update_id,token,message_id=100,query_id=None)`; no mock del repositorio.

- [ ] **1. Escribir tests RED** de seguridad/transacción:

```python
def test_callback_quantity_never_saves_and_replay_consumes_once(tmp_path):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    c.ingest_callback(2, c.choice_token("one_each"))
    first = c.repo.apply_guided_callback(2, now=c.now)
    assert c.repo.list_lines() == []
    assert c.repo.apply_guided_callback(2, now=c.now) == first
    assert c.repo.guided_state(2, now=c.now).snapshot.proposal.revision == 2
```

Añadir confirmación antes de entrega, callback antiguo tras edición, otra opción tras consumo, sí durante topic/scope, copia de aviso sin recibo conocido, query_id replay con payload distinto y failpoints antes/tras state/outbox. Al confirmar: assert exactamente tres filas solo después de evento final, y replay no cambia IDs/revisiones. Al rechazar tema: assert vieja revisión final ya no concede permiso.
- [ ] **2. Ejecutar** `python -P -m pytest tests/test_guided_storage.py tests/test_guided_provenance.py -q`; RED.
- [ ] **3. Implementar commit único**: cargar source+state+delivery en BEGIN IMMEDIATE, resolver tokens/texto según pregunta, reducir, emitir tokens persistidos, registrar Reply y resultado, consumir versión y aplicar mutations solo confirmed. Capturar token con `secrets.token_urlsafe(16)` y prefijo `q:`; no exponerlo a modelo. Validación de callback previa a reducción y final revalidación de fila/reserva.
- [ ] **4. Implementar procedencia v2** usando aportaciones y testigo de revisión para eventos callback auténticos; conservar lector v1. Append conserva condición/unidad/candidatos/decisiones y fuentes, nunca llama prepare_proposal para reemplazar el lote. Integrar record_delivery de tarea 3: solo una entrega cuyo notice/chat/digest coincida con revisión vigente completa su testigo, en la misma transacción; una revisión caducada no se reabre. Delivery de review no escribe lista. Descartar tema/editar regenera pregunta/testigo; consulta no renueva TTL.
- [ ] **5. Verificar** tareas 1–4 y suite completa. Tests de historial: tres pares solo del propietario, no tokens, event.query_id y payload privado no aparecen en prompts/logs; antecedentes inválidos fallan cerrado. Tests de revocación: fuente legacy huérfana reproduce el fallo anterior y no detiene runtime tras `/lista`.
- [ ] **6. Commit:** `feat: commit guided state with authenticated single-use choices`; revisión independiente especialmente de `confirmed` y comparación exacta source/notice/digest.

### Tarea 5: Teclados, callbacks autenticados y entregas inciertas

**Files:** modificar `telegram_io.py`; crear `tests/test_guided_telegram_io.py`; ampliar tests existentes de transporte sin reemplazar sus expectativas de autenticación.

**Consumes:** IncomingCallback, pending_replies/ingest_events/record_delivery y consumo del repositorio.
**Produces:** `TelegramIO.poll_once() -> None` para message+callback; `send_pending() -> None` serializa teclado y registra retorno de send_message; nuevo `ack_callbacks() -> None` usa métodos de acuse de tarea 3 y responde sin significado operativo. Llamarlo tras ingest antes de retornar poll_once y al recuperar callbacks duraderos, sin alterar schema10 ni guardar estado en memoria.

- [ ] **1. Escribir tests RED** usando Bot externo fake específico y repositorio real. Fixture `TelegramStub(bot_id=99)` ofrece get_updates/get_me/send_message/answer_callback_query y respuestas completas message/query de PTB22.5. Probar:

```python
def test_unregistered_message_cannot_authorize_a_known_token(tmp_path):
    c = persisted_case(tmp_path)
    # callback válido de propietario, pero message_id=999 no registrado.
    c.ingest_callback(2, c.choice_token("one_each"), message_id=999)
    c.repo.apply_guided_callback(2, now=c.now)
    assert [p.quantity for p in c.repo.guided_state(2, now=c.now).snapshot.proposal.items] == [None, None, None]
    assert c.repo.list_lines() == []
```

Tests de transporte observan inbox/outbox/recibos, no solo llamadas al fake: autorización incorrecta no persiste contenido, callback inaccesible/inline/game/manipulado rechazado, consulta legítima crea IncomingCallback y offset4; texto reenviado/citado sigue rechazado. Enviar summary astral oversized no crea teclado confirmable ni receipt de revisión.
- [ ] **2. Ejecutar** `python -P -m pytest tests/test_guided_telegram_io.py -q`; RED.
- [ ] **3. Implementar transporte** con `allowed_updates=['message','callback_query']`, chat/user/bot accesible validados y token format string. No confiar en CallbackQuery.data aunque exista el botón. Convertir Reply.keyboard a InlineKeyboardMarkup; summary con teclado no se fragmenta. Registrar ID/digest al retornar send_message antes de sent marker.
- [ ] **4. Implementar acuse persistido** inmediato tras ingest de callbacks, independiente del turno/operación; query expirada marca terminal el acuse, no reabre inbox ni bloquea notices. Reintentos de errores de red conservan estado. Teclado viejo puede desactivarse best effort fuera de la transacción; fallo no es fallo de negocio.
- [ ] **5. Verificar envíos inciertos/restart**: fake aplica envío y lanza NetworkError; segundo envío entrega mismo token, ambos solo conceden una transición desde IDs registrados. Callback de primera copia desconocida pide aviso vigente sin cambio. También pérdida tras record_delivery antes de sent_at y owner checks de ack. Suite completa y Ruff.
- [ ] **6. Commit:** `feat: transport durable guided Telegram interactions`; revisión de payload/auth/delivery antes de llamadas reales.

### Tarea 6: E4B acotado sin autoridad de alcance ni de guardado

**Files:** crear `shopping_agent/guided_ollama.py`, `tests/test_guided_ollama.py`; modificar solo skills existentes cuyos procedimientos necesiten mencionar foco/candidaturas/temas, conservando NOTICE/licencia, y `tests/guided_helpers.py` fixtures HTTP externos.

**Consumes:** GuidedState/GuidedAnswer y guided_history de tarea 4.
**Produces:** `GuidedOllamaAgent(model: str='gemma4:e4b-it-q4_K_M', *, transport: httpx.AsyncBaseTransport | None=None)` y `async interpret(event: IncomingMessage, state: GuidedState, history: tuple[dict,...]) -> GuidedModelResult`.

Schemas nativos exactos: `responder_cantidad(quantity, unit=None)` solo con foco individual/compartido seleccionado; `proponer_asignaciones(patches)` solo candidatos; `proponer_altas(items, condition=None)`; `proponer_cambio(kind, query, quantity=None, unit=None, replacement=None, condition=None)`; `consultar_lista()`; `consultar_ficha(query)`; `cancelar_propuesta()`; `pedir_aclaracion()`. Exponer únicamente el subconjunto pertinente: responder_cantidad no existe sin foco; una alta con borrador vigente es TopicCandidate. Guardar/confirmar/select-token no existen. Un turno puede devolver una sola sugerencia de cambio final; múltiples mutadores no se ejecutan ni se fusionan.

- [ ] **1. Escribir tests RED** con MockTransport a nivel HTTP, modelos y controlador reales:

```python
def test_no_focus_only_produces_candidate_not_changes():
    # HTTP fixture propone una unidad para las tres posiciones.
    result = run_interpret_with_fixture("candidate_all", message(2, "Pon uno"), state_fixture())
    decision = reduce_guided(state_fixture(), message(2, "Pon uno"), result.answer, now=NOW)
    assert decision.mutations == ()
    assert [p.quantity for p in decision.state.snapshot.proposal.items] == [None, None, None]
    assert decision.state.question.kind == "scope"
```

Definir helper `run_interpret_with_fixture(name,event,state,history=()) -> GuidedModelResult` en tests del módulo; fixtures replican done/done_reason y argumentos reales, no solo texto. Tests: foco seleccionado 2 se aplica solo a posiciones ofrecidas; edición de posición ya completa pasa a candidatura/correct-choice, no se borra; nueva leche produce TopicCandidate sin position4; kind confirm/refusal/schema extra/NaN/truncado produce reason invalid; ninguna prosa entra Reply. Nombres sí/todos y prompt injection de producto son datos.
- [ ] **2. Ejecutar** `python -P -m pytest tests/test_guided_ollama.py -q`; RED.
- [ ] **3. Implementar un runner acotado** manteniendo parámetros/presupuesto global, con schemas inlined sin $refs colgantes. Contexto app incluye pregunta y foco, propiedades necesarias completas y hasta tres pares. Construir source_update_id de GuidedAnswer desde event, nunca aceptar ese campo en schemas nativos ni seleccionar un evento pasado arbitrario. No filtrar conflictos/unidades/condiciones para ganar bytes. Sin literal-citation como autorización y sin confidence threshold que conceda alcance.
- [ ] **4. Verificar límites**: overflow24.000 bytes, cuatro llamadas/ocho tools, timeout120s, respuesta sin herramienta, desconocida y múltiple; todos dan candidata/clarificación sin efectos. La metadata de autoridad/token/config no aparece en prompt. Tests offline no llaman Ollama ni Settings.
- [ ] **5. Commit:** `feat: interpret focused answers as controlled candidates`; revisar conjuntamente con controlador que ningún resultado del modelo crea ResolvedChoice ni ReviewWitness.

### Tarea 7: Conversación guiada, opt-in y rollback operativo

**Files:** crear `shopping_agent/guided_conversation.py`, `tests/test_guided_conversation.py`, `tests/test_guided_runtime.py`; modificar `config.py`, `cli.py`, `runtime.py` y `shopping_agent/conversation.py` únicamente para revocar preguntas al ceder a rutas incompatibles; actualizar colaboradores de transporte en `tests/test_agent_runtime.py` sin cambiar sus oráculos de motores.

**Consumes:** repo/task4, transport/task5, model/task6 y controlador/task2.
**Produces:** `GuidedConversation(repo: Repository, agent: GuidedOllamaAgent, legacy: Conversation, *, clock=None)` y `async handle(event: IncomingEvent, mode: str) -> Reply`; `Settings.guided_questions: bool=False`; `async guided_local(root: Path, action: str) -> bool` y comando CLI `questions-local enable|disable|status`.

Orden de handle: comprobar durable identity y replay; callback va a apply_guided_callback; mensaje slash/compras mantiene rutas legacy y revoca preguntas que entrarían en conflicto; selección/control textual se resuelve según QuestionKind; consultas conservan preguntas; turno libre llama interpret y aplica expected_question_version en repo. No llamar apply_agent_control legacy antes de resolver pregunta topic/scope; `sí` contextual jamás es confirmación genérica. Model/config no se cargan en transporte.

- [ ] **1. Escribir tests RED** de ruta completa sin red privada:

```python
def test_topic_no_preserves_main_and_scope_yes_does_not_save(guided_session):
    guided_session.propose(["huevos", "carne", "atun"])
    guided_session.new_topic("leche")
    guided_session.send("no")
    assert guided_session.pending_names() == ["huevos", "carne", "atun"]
    assert guided_session.saved() == []
```

Definir fixture guided_session en este fichero sobre Repository real, transport stub y HTTP fixture de tarea 6; métodos no simulan efectos. Tests del flag defaultFalse, error True+legacy/provider inválido, status read-only con worker lock, save_settings fallido después de revocar, rollback mismo código en schema10, comandos `/lista` tras caducidad y callback retenido cuando flag apagado que devuelve inactivo sin pasar a legacy. Corrección «sí pero...» regenera review y siguiente sí guarda una sola vez.
- [ ] **2. Ejecutar** `python -P -m pytest tests/test_guided_conversation.py tests/test_guided_runtime.py -q`; RED.
- [ ] **3. Implementar construcción opt-in** en runtime y procesamiento pending_events; si flag apagado, mensajes conservan motor seleccionado y callbacks retenidos se completan controladamente sin mutación. ack_callbacks antes de turnos lentos. Mantener recovery, checkout y ProcessLock actuales.
- [ ] **4. Implementar CLI** con worker parado para enable/disable; enable exige skills_agent+ollama+E4B disponible, revoca antes de save. Desactivar model-local/agent-local fuerza guided_questionsFalse y revoca tokens/tema/revisión. No ejecutar estos comandos contra settings privados en esta tarea.
- [ ] **5. Verificar** tests nuevos, `tests/test_agent_runtime.py` y suite completa. Owner assertions se ejecutan antes de dispatch de ambos tipos. Definir en `tests/guided_helpers.py` un PurchaseBlockedRepository que rechaza buy/resume en el borde de escritura y guard de conversación para compras naturales/comandos: assert pending_orders/resumable_orders vacíos y checkout nunca ejecutado. Es adaptador de pruebas, no permiso de lanzar runtime normal en Telegram; no construir perfil/store. Documentar el launcher aislado/bloqueado que habrá que preparar bajo autorización de lanzamiento antes de reemplazar worker real.
- [ ] **6. Commit:** `feat: opt into persistent guided conversations`; revisión end-to-end del flag apagado y rollback antes de aceptación real.

### Tarea 8: Matriz de aceptación, conversaciones reales y documentación de límites

**Files:** crear `scripts/probe_guided_questions.py`, `tests/test_guided_acceptance.py`, `docs/superpowers/evidence/2026-10-09-preguntas-guiadas/{matrix.json,execution-status.md,results.md}`; modificar `README.md` para uso/rollback. No copiar scripts temporales.

**Consumes:** sistema integrado tareas 1–7, transporte de tests para acreditar entregas y controles reales.
**Produces:** CLI de probe `--mode offline|real --output PATH --repetitions 3`; opción `--verify PATH` recalcula oráculos sin llamar al modelo. Evidencia cruda JSONL incluye inputs/callback selections/model output/validations/questions/revisions/delivery/saved rows; no datos privados.

- [ ] **1. Congelar matrix.json ANTES de ejecutar**: todos los casos previos y variantes nuevas, expectativas de estado por paso independientes del programa. Incluir cantidades reordenadas, respuestas parciales, grupo explícito/ambiguo, consulta+respuesta, tema nuevo+no/append, condición/duplicados/unidad, legacy expirado, corrección post-review, confirmación mixta y repetida. Cada conversación tiene camino por botones y texto libre acotado; agrupar los nuevos casos de general free language separados, no promediar fallos de seguridad.
- [ ] **2. Escribir tests RED del verificador/harness**: evidence con cantidad equivocada, filas guardadas antes de confirm, un duplicado interno sin decisión y una entrega faltante debe devolver nonzero. Afirmar que no importa config/load_settings ni accede a private; el input inválido no pasa por oráculo calculado del controlador. Guardar fixture literalmente esperado.
- [ ] **3. Implementar probe aislado** con repositorios sintéticos y recibos de transporte reales del stub; E4B real solo en modo real, modelo/parámetros fijos, sin descargar nada. Repetir tres veces y registrar errores/steps no ejecutados cuando una conversación se detenga. Botones simulados se etiquetan, nunca contarlos como comprensión del modelo.
- [ ] **4. Ejecutar offline y real** en la venv existente con PYTHONPATH del worktree de ejecución; guardar resultados crudos completos. Esperado para activar: todas las invariantes, todas las conversaciones guiadas y libres ACOTADAS terminan, cero asignaciones ambiguas aplicadas/cero escrituras sin confirmación. Un fallback sin perder datos no es automáticamente un pass de interpretación.
- [ ] **5. Verificar evidencia independientemente** con `--verify`, hashes de matriz/script/código y parámetros. Resolver consulta de lista/duplicados internos originales como parte de los caminos pertinentes; si alguno falla, dejar aceptación bloqueada. No cambiar matriz/prompt después del run sin versionar el experimento y volver a comparar.
- [ ] **6. Verificación final** `python -P -m pytest -q`, `python -P -m ruff check .`, `git diff --check`. Inspeccionar distribución con herramientas instaladas; si wheel sigue no verificable, anotarlo claramente y no instalar dependencias ni afirmar packaging correcto. Whole-branch review de contratos, transacciones, transport y seguridad; nuevos bugs llevan su propio RED→GREEN y reejecución afectada.
- [ ] **7. Documentar resultados y commit:** `test: record guided conversation acceptance and limits`. Registrar explícitamente pendientes, límites colectivos libres, pruebas reales/simuladas, callbacks duraderos y rollback. No cerrar Task7 anterior sin evidencia que resuelva sus fallos. Handoff al usuario para autorizar cualquier prueba Telegram nueva; no ejecutar stop/start/merge/push en esta tarea.

## Comandos y condiciones de verificación

En PowerShell del worktree de ejecución, utilizar el Python existente, sin instalar:

```powershell
$env:PYTHONPATH = "$PWD"
& 'C:\Users\Takeshi\Documents\projects\project_shop_assistant\.venv\Scripts\python.exe' -P -m pytest -q
& 'C:\Users\Takeshi\Documents\projects\project_shop_assistant\.venv\Scripts\python.exe' -P -m ruff check .
git diff --check
```

Sustituir `python -P` de los pasos por esa ruta cuando python del PATH no sea la venv. Si falta Ollama/model/backend build, reportar bloqueo; no aumentar límites ni instalarlo sin autorización. Cada tarea enumera sus tests rápidos, pero el gate completo requiere la suite existente y nueva; señalar cualquier fallo por nombre aunque no se originara en la tarea.

## Cobertura de la especificación y handoff

| Secciones de spec | Tareas |
| --- | --- |
| 1–3: objetivo, límites de evidencia y enfoque híbrido | Constraints, 2, 6, 8 |
| 4: cantidades/correcciones/temas/controles | 2, 4, 6, 7 |
| 5–6: componentes, estado, procedencia e historial | 1, 2, 3, 4 |
| 7: Telegram autenticado e idempotente | 3, 4, 5 |
| 8: revisión íntegra entregada y confirmación | 1, 2, 4, 5, 7 |
| 9: respuesta libre sin conceder alcance | 2, 6, 8 |
| 10: opt-in, rollback y lanzamiento aislado | 3, 4, 7, 8 |
| 11–12: aceptación, documentación y gates | 8 y revisión antes de ejecución |

No hay implementación iniciada por escribir este plan. Revisarlo y elegir método:
subagentes con gates por tarea y revisión global, o ejecución nativa con revisión
global independiente. Recomendación: subagentes, por las ocho unidades y el coste
de un fallo de procedencia/confirmación; mayor coste de contextos, no trabajo
paralelo sobre contratos compartidos. El usuario puede preferir ejecución nativa.
