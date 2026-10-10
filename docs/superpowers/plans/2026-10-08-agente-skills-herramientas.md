# Agente con skills adaptadas y herramientas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Comprender peticiones naturales de varios productos mediante E4B y skills adaptadas, con propuestas revisadas antes de cualquier cambio de lista.

**Architecture:** Un agente con herramientas nativas interpreta; un reductor puro prepara lotes y un repositorio transaccional valida y confirma. La aplicación emite resultados operativos, sin redactor adicional. La integración opt-in preserva comandos, recuperación histórica y rollback.

**Tech Stack:** Python >=3.12, Pydantic existente, SQLite, httpx existente, pytest/Ruff, Ollama local; ninguna dependencia nueva.

**Spec:** `docs/superpowers/specs/2026-10-08-agente-skills-herramientas-design.md`

## Global Constraints

- Un agente local `gemma4:e4b-it-q4_K_M`, con skills precargadas y herramientas nativas.
- Todo cambio de la lista originado por el agente requiere una propuesta visible y confirmación explícita, incluidas altas nuevas y cantidades pendientes.
- Mantener la caducidad de 15 minutos y la persistencia tras reinicio.
- Un lote se guarda completo en una transacción o no se guarda; nunca aplicar parcialmente una propuesta fallida.
- Ninguna llamada a Ollama ni espera de red ocurre dentro de la transacción SQLite.
- No activar, reiniciar, cambiar el modelo del bot, acceder a datos privados o publicar como consecuencia de aprobar este documento.
- Implementar posteriormente en un worktree nuevo desde la rama integrada.
- Conservar listas históricas, pedidos, reservas, offsets, inbox/outbox y trabajos de presentación v1/v2.
- No introducir frameworks de agentes, vector DB, multiagentes, descarga dinámica de skills ni una segunda capa de interpretación de lenguaje natural.
- Adaptar solo ejemplos MIT de Shopping List; conservar atribución/licencia. No instalar OpenClaw, AnyList, Trello ni CLIs externos.

## Review Focus

1. «Sí, pero cambia la carne»: no autoriza el resumen anterior; editar exige otra revisión (T2/T6).
2. Nueva fila duplicada después del resumen: ni siquiera un alta sin fila objetivo debe eludir la nueva decisión de duplicado (T3).
3. Dos operaciones del lote apuntan a la misma fila o crean duplicados entre sí: resolver el conflicto antes del resumen (T2/T3).
4. Respuesta con dos herramientas mutadoras, una inválida o instrucciones dentro de títulos: no ejecutar parcialmente ni adquirir permisos (T4/T5).
5. Desactivar/reactivar el agente con un «sí» en inbox: no reutilizar permisos de otra ruta o sesión (T3/T6).

## Preparación y mapa de archivos

Ejecutar desde un worktree nuevo creado mediante `using-git-worktrees`, después de aprobación del plan/método. Base de producto `28af475`; incluir documentos aprobados de la rama actual. Verificar estado limpio y suite base antes de cambiar producto. No eliminar worktrees anteriores ni reutilizar artefactos temporales del spike.

En PowerShell, `python` en los comandos siguientes significa el ejecutable de `.venv\Scripts\python.exe` del checkout original, con `PYTHONPATH` apuntando al worktree. No crear/copiar un entorno ni instalar dependencias si el existente sirve. Para empaquetado usar `python -m pip wheel --no-deps --no-build-isolation --wheel-dir <temp-aprobado> .` y comprobar el ZIP; no consultar índices ni instalar el wheel en el bot.

Crear un paquete `shopping_agent` para mantener juntas estas responsabilidades:
- `contracts.py`: argumentos, propuestas, referencias, resultados; sin IO.
- `proposals.py`: transición pura y aritmética, sin SQL/modelo.
- `replies.py`: representación operativa determinista y segmentación.
- `storage.py`: mixin del Repository para propuestas, procedencia y commits.
- `tools.py`: catálogo nativo y dispatcher tipado.
- `ollama.py`: transporte HTTP y bucle finito de herramientas.
- `conversation.py`: frontera de integración, rutas explícitas y control.
- `skills.py`, `skills/*.md`: carga fija local y cuatro guías breves.
- `__init__.py`: paquete sin efectos al importar.

Modificar `storage.py`, `config.py`, `runtime.py`, `cli.py`, `pyproject.toml`; añadir `migrations/009.sql`. Mantener el intérprete/reductor antiguo para modo legacy y recuperación, no refactorizar sus gramáticas. Pruebas nuevas `tests/test_agent_*.py`, apoyo `tests/agent_support.py`, probe `scripts/probe_skills_agent.py`.

### Task 1: Contratos y skills adaptadas

**Files:** Create `shopping_agent/__init__.py`, `shopping_agent/contracts.py`, `shopping_agent/skills.py`, `shopping_agent/skills/{consultar,altas,cambios,propuestas}.md`, `third_party/shopping-list-skill/{LICENSE,NOTICE.md}`; modify `pyproject.toml`; test `tests/test_agent_contracts.py`, `tests/test_agent_skills.py`.

**Interfaces:**
- `load_skills() -> str`: orden fijo consultar/altas/cambios/propuestas, mediante recursos del paquete; ninguna ruta recibida del modelo.
- Todos los modelos heredan `domain.Model` (strict, frozen, extra forbid). Reutilizar `dialogue.PackageQuantity`, `LineRef`, `Unit`, `DIALOGUE_TTL`, `canonical_name`.
- `ItemInput(description: str, quantity: PackageQuantity | None = None, unit: Unit | None = None)`; descripción no vacía, máximo 160 caracteres; no convertir `unit=None` en permiso para pañales.
- `ProposeAdds(items: tuple[ItemInput, ...], condition: str | None = None)`; 1..20 productos, condición no vacía máximo 500 caracteres si presente.
- `ProposeChange(kind: Literal['increment','set_quantity','replace'], query: str, quantity: PackageQuantity | None = None, unit: Unit | None = None, replacement: str | None = None, condition: str | None = None)`; destino exclusivo/obligatorio para replace.
- `CompleteProposal(patches: tuple[ItemPatch, ...], remove_condition: bool = False)`; `ItemPatch` identifica posición 1..20, puede aportar cantidad/unidad, índice de candidato, decisión `separate` o `set_total`. No incluye permisos, IDs de usuario ni confirmaciones.
- `ProposalItem`: posición, tipo de operación, descripción, cantidad/unidad, candidatos `tuple[LineRef,...]`, target `LineRef | None`, base/delta, decisión de duplicado y firmas de conflictos. Todos calculados por aplicación excepto los datos del ItemInput.
- `AgentProposal`: schema_version=1, id UUID de aplicación, revision entera positiva, user/chat, source_update_id, original_text, items, condition, updated_at/expires_at, reviewed_revision/update_id opcionales. Revisión visible solo si todos los ítems están completos y no hay condición.
- `AgentSnapshot`: proposal opcional, líneas y reservas completas de aplicación, contexto de origen. No serializar identidad ni permisos en contexto del modelo.
- `ProposalDecision`: propuesta siguiente opcional, motivo tipado y `mutations: tuple[DialogueMutation,...] = ()`; solo controles explícitos pueden devolver mutations.
- `ToolCall(name: str, arguments: dict)`, `ToolResult(name: str, data: dict, reply: Reply, terminal: bool)`; `AgentRunResult(reply: Reply, model_calls: int, tool_calls: int, reason: str)`.

- [ ] **Step 1 — RED:** Tests `test_strict_quantities_and_arguments` rechazan bool/float/0/negativo/2**63/campos `confirmed`, usuario o SQL; `test_items_bounded_and_names_preserved` conserva marca/etapa/gramos y rechaza 21 ítems; `test_skill_resources_are_fixed_and_attributed` exige cuatro guías, procedencia MIT, límites de tamaño (cada guía <=500 palabras) y ninguna instrucción de escribir ficheros/ejecutar comandos.

  Test mínimo de contrato:
  ```python
  @pytest.mark.parametrize('quantity', [True, 1.5, 0, -1, 2**63])
  def test_strict_quantities_and_arguments(quantity):
      with pytest.raises(ValidationError):
          ItemInput(description='arroz', quantity=quantity)

  def test_items_bounded_and_names_preserved():
      item = ItemInput(description='Blemil Evolution 1 800 g')
      assert item.quantity is None
      assert item.description == 'Blemil Evolution 1 800 g'
      with pytest.raises(ValidationError):
          ProposeAdds(items=(item,) * 21)
  ```
- [ ] **Step 2:** Run `python -m pytest tests/test_agent_contracts.py tests/test_agent_skills.py -q`; exigir fallos por contratos ausentes.
- [ ] **Step 3 — GREEN:** Implementar contratos y carga fija. Adaptar ejemplos de varios productos y ambigüedad de `references/commands.md` del commit upstream `e37617947cd8e8aa095c5a358c9005bb2ac1c6fd`; conservar LICENSE MIT íntegra y NOTICE con URL/revisión/fragmentos adaptados. Skills describen nuestros nombres de herramientas, nunca SQL/archivos. Ejemplos: arroz+carne sin cantidad; varias cantidades por nombre; ambigüedad entre leche entera/avena; condiciones y negaciones; ninguna cantidad inventada. Empaquetar assets mediante package-data y añadir `shopping_agent` a packages.
- [ ] **Step 4:** Repetir comando, exigir PASS; verificar que distribución construida contiene las cuatro guías sin introducir dependencia de runtime.
- [ ] **Step 5:** Commit archivos de esta tarea: `feat: add strict agent contracts and adapted MIT skills`.

### Task 2: Propuestas puras y representación veraz

**Files:** Create `shopping_agent/proposals.py`, `shopping_agent/replies.py`, `tests/agent_support.py`; test `tests/test_agent_proposals.py`, `tests/test_agent_replies.py`.

**Interfaces:**
- `prepare_proposal(message: IncomingMessage, args: ProposeAdds | ProposeChange, snapshot: AgentSnapshot, *, now: datetime) -> ProposalDecision`.
- `complete_proposal(message: IncomingMessage, args: CompleteProposal, snapshot: AgentSnapshot, *, now: datetime) -> ProposalDecision`.
- `parse_control(text: str, proposal: AgentProposal | None, *, now: datetime) -> DialogueAnswer | None`: confirm solo mensaje entero normalizado `sí`, `confirmo`, `confirmar`; rechazo `no`, cancelación `cancelar`; selección/cantidad solo ante pregunta compatible. Fuera de contexto no crea permiso. Un mensaje mixto nunca es confirmación.
- `answer_proposal(message: IncomingMessage, snapshot: AgentSnapshot, *, now: datetime) -> ProposalDecision`: reparsa controles; revalidación completa y permiso vinculado a reviewed_revision y versión actual.
- `render_proposal(decision: ProposalDecision, snapshot: AgentSnapshot) -> Reply`; `render_tool_results(results: tuple[ToolResult,...]) -> Reply`; nunca texto libre de modelo.

- [ ] **Step 1 — RED:** `test_multi_add_waits_for_all_quantities_and_review`: preparar arroz/carne devuelve 2 pendientes y cero mutations; completar 2/3 sigue sin mutations; revisión seguida de `sí` produce dos altas. `test_duplicate_and_increment_require_selection` conserva ambas filas de arroz, obliga elegir y muestra 1+2=3. `test_unknown_base_is_not_zero`, `test_diaper_unit_and_overflow`, `test_cancel_only_discards_proposal`, `test_condition_blocks_confirmation`, `test_same_target_twice_and_internal_duplicates_block_review`, `test_mixed_yes_edit_cannot_commit` y `test_social_read_does_not_renew_ttl` fijan los límites.
- [ ] **Step 2:** Run `python -m pytest tests/test_agent_proposals.py tests/test_agent_replies.py -q`; confirmar RED.
- [ ] **Step 3 — GREEN:** Implementar reductor sin IO. Matching conserva variantes; coincidencias múltiples siempre ofrecen candidatos, nunca escoger la primera. Guardar firmas de conflictos canónicos con revisión, incluidos duplicados internos. Incremento sin coincidencia ofrece alta nueva, sin convertir «más» en nombre; base desconocida ofrece total, nunca suma. Edición incrementa revision y borra reviewed_*; retirar condición es una edición explícita, no confirmación.
- [ ] **Step 4:** Construir preguntas/selecciones completas, pendientes fuera de lista, petición original y resumen completo. Resumen termina «Pendiente, sin guardar. ¿Confirmas?». Mostrar duplicado como nueva línea separada o cambio total. Rechazar salida demasiado larga antes de habilitar revisión: Reply es un único mensaje, máximo 4000 caracteres; pedir reducir/dividir lote, nunca truncar hechos para confirmar. Test `test_oversized_review_cannot_grant_permission` y `test_reply_covers_every_item_candidate_and_operand`.
- [ ] **Step 5:** Repetir tests, exigir PASS; commit `feat: prepare reviewed batch proposals without list writes`.

### Task 3: Persistencia, confirmación atómica y procedencia

**Files:** Create `shopping_agent/storage.py`, `migrations/009.sql`; modify `storage.py:42-85,123-145`; test `tests/test_agent_storage.py`, `tests/test_agent_recovery.py`, `tests/test_dialogue_storage.py`, `tests/test_storage.py`.

**Interfaces:** `AgentRepository` mixin añadido a `Repository`.
- `agent_snapshot(update_id: int, *, now: datetime) -> AgentSnapshot`: identidad/texto proceden de inbox; cargar filas/reservas dentro de lectura breve; datos completos para controlador, contexto separado/acotado para Gemma.
- `apply_agent_operation(update_id: int, name: str, arguments: dict, expected_revision: int | None, *, now: datetime) -> ToolResult`: validar catálogo/contratos en la transacción, no confiar en ProposalDecision recibido del modelo.
- `apply_agent_control(update_id: int, *, now: datetime) -> Reply | None`: reparsar texto duradero y generar/confirmar decisión en la transacción; sin booleano confirm externo.
- `complete_agent_reply(update_id: int, reply: Reply) -> Reply`: `_complete_reply` existente; resultado operacional interno, no argumentos del modelo.
- `set_conversation_route(user_id: int, chat_id: int, route: Literal['legacy','agent'], *, now: datetime) -> bool`: detectar cambio de ruta y revocar SOLO contexto conversacional, aviso de reformular; retorna si cambió.
- `_record_command_origin(db: sqlite3.Connection, source: sqlite3.Row) -> None` y `command_origin(user_id: int, chat_id: int) -> IncomingMessage | None`: prueba de inbox del comando que creó el contexto; validar texto slash/purchase autorizado; desconocido no autoriza continuación. El helper privado comparte la transacción de diálogo, nunca abre un commit aparte.

- [ ] **Step 1 — RED:** `test_propose_and_complete_never_insert_list_lines`; `test_confirm_commits_full_batch_and_one_notice`; `test_replay_and_second_yes_do_not_repeat`; `test_failure_on_second_write_rolls_back_everything`; `test_target_revision_reservation_and_new_duplicate_invalidate`; `test_forged_confirmation_or_foreign_owner_is_rejected`; `test_v8_migration_preserves_all_old_tables`; `test_route_toggle_revokes_old_yes`; `test_persisted_corruption_cannot_grant_permission`.
- [ ] **Step 2:** Run `python -m pytest tests/test_agent_storage.py tests/test_agent_recovery.py -q`; exigir RED.
- [ ] **Step 3 — GREEN:** Migration v9 crea `agent_proposals(user_id,chat_id,proposal_json)` con clave compuesta y `conversation_routes(user_id,chat_id,route,command_update_id)` enlazado a inbox. No borrar diálogo al migrar ni tocar otras tablas. Actualizar límite/version de migración y pruebas que afirmaban versión 8 a 9; preservar snapshots v5/v8. Extender owner assertion a ambas tablas y procedencia referenciada.
- [ ] **Step 4:** Implementar métodos usando `_connection(write=True)`, `_complete_reply`, `_lines`, `_find_products`, `resolve_product`. Preparar/completar/cancelar propuesta y resultado inbox/outbox en la MISMA transacción; una operación terminal no necesita job nuevo ni otra llamada al modelo. reviewed_revision/update_id solo se escriben cuando render_proposal genera el resumen íntegro <=4000 caracteres y su outbox se compromete conjuntamente. Confirmación valida TTL, revisión revisada, origen original/de revisión, candidatos, reservas y duplicados actuales; mutations solo dentro de este método. Rowcount debe ser 1 en updates. Conflicto => cero cambios de lista, propuesta sin permiso y revisión requerida. Social/consulta no escribe ni renueva propuesta. Nunca usar `_apply(add)` como herramienta natural.
- [ ] **Step 5:** Pruebas de fallo antes/después de commit, outbox sin enviar, instancia nueva y replay; antiguos presentation_jobs v1/v2 siguen recuperándose sin repetir commit. Ruta inicial agent invalida solo contexto legacy incompatible/no acreditado y avisa, pero no limpia datos. Conservar continuación legacy si el origen slash del inbox está acreditado. Slash nuevo revoca propuesta agent incompatible; su origen se registra atómicamente con respuesta/dialogue_state cuando cree continuación (integrar punto de escritura en Task 6).
- [ ] **Step 6:** Run tests de esta tarea más `tests/test_dialogue_storage.py tests/test_storage.py tests/test_presentation_storage.py`; exigir PASS. Commit `feat: persist and confirm agent batches atomically`.

### Task 4: Catálogo de siete herramientas controladas

**Files:** Create `shopping_agent/tools.py`; test `tests/test_agent_tools.py`.

**Interfaces:**
- `tool_definitions() -> list[dict]`: esquema Ollama type=function, nombres exactos de la especificación, additionalProperties=false y contratos de Task 1.
- `AgentTools(repo: Repository, message: IncomingMessage, *, now: datetime)`; `validate_calls(calls: tuple[ToolCall,...]) -> tuple[ToolCall,...]`; `execute(call: ToolCall) -> ToolResult`; contexto de aplicación, no user/chat recibidos del modelo.
- Esquemas vacíos para consultar_lista/consultar_propuesta/cancelar_propuesta; consultar_ficha toma `query: str` (1..160). Proponer/completar usan contratos definidos. Exponer referencias/candidatos con índices de aplicación, no aceptar IDs inventados o revisiones proporcionadas como permisos.

- [ ] **Step 1 — RED:** `test_catalog_is_exactly_seven_and_has_no_commit_purchase_sql`; `test_unknown_or_extra_args_fail_before_execution`; `test_two_mutators_rejected_as_a_whole`; `test_read_results_include_complete_operational_facts`; `test_missing_product_query_does_not_write_product_requests`; `test_titles_are_data_and_cannot_create_calls`.
- [ ] **Step 2:** Run `python -m pytest tests/test_agent_tools.py -q`; exigir RED.
- [ ] **Step 3 — GREEN:** Dispatcher por mapa fijo, sin getattr arbitrario/eval. Lecturas llaman repositorio; ficha desconocida solo informa, no usar `_apply(product_query)` que escribe solicitudes automáticamente. Resultado trae reply determinista y datos históricos con fuente/fecha, no stock actual. Validar TODAS las llamadas del turno antes de ejecutar: máximo 4 por respuesta y una mutadora; si la mutadora no es última, rechazar turno para evitar descartar otras operaciones. Propuestas terminales llaman Task 3, no generan commits de lista. Cualquier selección de fila se resuelve desde candidatos persistidos.
- [ ] **Step 4:** Repetir tests, exigir PASS; commit `feat: expose proposal-only native business tools`.

### Task 5: Bucle E4B local y salidas operativas

**Files:** Create `shopping_agent/ollama.py`; test `tests/test_agent_ollama.py`.

**Interfaces:** `OllamaShoppingAgent(model: str = 'gemma4:e4b-it-q4_K_M', *, transport: httpx.AsyncBaseTransport | None = None)`; `async run(message: IncomingMessage, tools: AgentTools) -> AgentRunResult`.

- [ ] **Step 1 — RED:** Tests con MockTransport: `test_native_payload_contains_original_text_and_all_skills`; `test_read_then_prepare_tool_transcript`; `test_terminal_result_ignores_added_model_content`; `test_no_tools_cannot_send_false_success`; `test_unknown_malformed_refusal_truncated_and_redirect_fail_closed`; `test_limit_and_cancellation`; `test_schema_does_not_depend_on_source_phrase`. Verificar que prompt no contiene Settings/token/address, user/chat, reviewed permisos ni paths privados.
- [ ] **Step 2:** Run `python -m pytest tests/test_agent_ollama.py -q`; exigir RED.
- [ ] **Step 3 — GREEN:** `/api/chat` HTTP directo, endpoint fijo `http://127.0.0.1:11434`, trust_env=false, redirects=false, stream=false, think=false; temperature=0, num_ctx=8192, num_predict=512. No `format=Intent` ni schema elegido por regex. Timeout global 120 s (incluye cold load), conexión 2 s; máximo 4 llamadas modelo y 8 herramientas totales. Validar done=true/done_reason=stop, assistant role, tool_calls list y argumentos object estrictos. Añadir assistant completo y mensajes role=tool/tool_name tras lecturas; no reenviar resultados como instrucciones de sistema.
- [ ] **Step 4:** Una mutadora válida es terminal: usar su respuesta ya comprometida, sin llamada de redacción posterior. Turnos de solo lectura acumulan resultados operativos; al finalizar/agotar límite devolver esos resultados y estado real, nunca prose del modelo. Sin herramientas y sin ruta greeting conocida, aclaración controlada; no intentar verificar texto arbitrario mediante otro modelo o whitelist de peticiones. El greeting social de aplicación se mantiene en Task 6. No afirmar conversación social ilimitada como criterio de esta entrega. CancelledError propaga; sin mutación queda inbox pendiente para retry, después de mutación terminal el resultado es recuperable.
- [ ] **Step 5:** Repetir tests, exigir PASS; commit `feat: run bounded local E4B native tool conversations`.

Referencia de protocolo consultada: Ollama `docs/api.md` y `docs/capabilities/tool-calling.mdx` (Context7 `/ollama/ollama`), assistant.tool_calls.function.arguments object y respuesta role=tool con tool_name. No instalar SDK adicional.

### Task 6: Integración opt-in, comandos y rollback

**Files:** Create `shopping_agent/conversation.py`; modify `conversation.py`, `dialogue_storage.py`, `config.py`, `runtime.py`, `cli.py`; test `tests/test_agent_conversation.py`, `tests/test_agent_runtime.py`, `tests/test_ollama_interpreter.py`, `tests/test_runtime.py`; modify documentación de uso `README.md`.

**Interfaces:** `AgentConversation(repo: Repository, agent: OllamaShoppingAgent, legacy: Conversation, *, clock: Callable[[], datetime] | None = None)`; `async handle(message: IncomingMessage, mode: str) -> Reply`. Settings añade `conversation_engine: Literal['legacy','skills_agent'] = 'legacy'`, `agent_model: Literal['gemma4:e4b-it-q4_K_M'] = 'gemma4:e4b-it-q4_K_M'`; ollama_model legacy E2B sin cambios. Skills_agent exige model_provider=ollama por validador.

- [ ] **Step 1 — RED:** `test_durable_results_and_old_presentations_precede_agent`; `test_known_greeting_reads_no_rows_and_preserves_pending`; `test_natural_alias_never_falls_into_old_parser`; `test_complete_yes_control_calls_no_model`; `test_mixed_yes_edit_uses_agent_and_new_review`; `test_commands_purchase_and_command_origin_continuations_stay_legacy`; `test_enable_disable_does_not_resurrect_proposal`; `test_runtime_default_remains_legacy`; `test_configuration_lock_and_secret_safety`.
- [ ] **Step 2:** Run `python -m pytest tests/test_agent_conversation.py tests/test_agent_runtime.py -q`; exigir RED.
- [ ] **Step 3 — GREEN:** Orden: inbox identity/result; prepared v1/v2 por legacy `_present`; sincronizar route epoch; slash/purchase explícito por legacy; greeting completo conocido sin snapshot/lista; controles propios por repo; continuación legacy solo si origen inbox slash verificado; resto llama agente. No `parse_command`/classify_request/validate_request en la interpretación natural del nuevo camino, salvo el atajo greeting estrictamente existente. Si reconoce control sin permiso, respuesta no_pending sin llamar modelo. Compras jamás proceden del resultado de herramientas.
- [ ] **Step 4:** Registrar comando-origen dentro de la transacción de `_apply_dialogue` cuando un slash genera state; limpiar vínculo al terminar/cancelar/iniciar propuesta incompatible. Wrapper legacy opcional en `Conversation.handle` sincroniza route para invalidar pendientes agent tras rollback; recuperar trabajo previo antes de invalidar contexto. Añadir aviso controlado si se descarta memoria incompatible. No reescribir trabajos comprometidos ni migrar un permiso antiguo a uno nuevo.
- [ ] **Step 5:** Runtime crea AgentConversation solo con opt-in; no crea OllamaReplyWriter para este camino. CLI añadir subcomando `agent-local enable|disable|status`: usar ProcessLock, comprobar modelo con ollama_available, enable configura engine/provider explícitos sin alterar legacy ollama_model; disable solo engine=legacy (provider conserva configuración válida). Cada enable/disable explícito revoca la propuesta agent actual bajo lock ANTES de guardar settings, incluso si no hubo mensajes entre disable y enable; un fallo posterior no recupera ese permiso. Status/doctor son solo lectura. Nunca ejecutar estos comandos en los datos reales durante desarrollo. Doctor muestra motor/modelo, sin descargar ni generar texto. Documentar modelo instalado, activación por separado y rollback sin permisos residuales.
  El comando existente `model-local disable` también pasa engine a legacy y revoca propuesta para conservar configuración válida con commands_only; `model-local enable` no activa skills_agent automáticamente. Revalidar Settings tras model_copy antes de persistir. Añadir `test_model_local_disable_from_agent_is_valid_and_revokes_permission` con configuración/repositorio temporales, sin Telegram.
- [ ] **Step 6:** Repetir tests de esta tarea y existentes de runtime/config/CLI; exigir PASS. Commit `feat: integrate opt-in skills agent without changing default bot`.

### Task 7: Aceptación offline y E4B real aislado

**Files:** Create `tests/test_agent_end_to_end.py`, `tests/test_agent_probe.py`, `scripts/probe_skills_agent.py`; create evidencia `docs/superpowers/evidence/2026-10-08-skills-agent/` durante ejecución.

**Interfaces:** Probe independiente usa Repository temporal, AgentConversation real, Tools reales y OllamaShoppingAgent real. `--offline` inyecta HTTP simulado explícitamente; default usa E4B real local. `--output <path>` obligatorio, rechaza destino dentro de `private`; no carga Settings/Telegram/browser/checkout. Exit 0=PASS, 1=FAIL, 2=PENDING (modelo ausente/inaccesible). stdout JSONL sintético con métricas separadas.

- [ ] **Step 1 — RED:** `test_runtime_multi_product_flow_needs_confirm`; `test_increment_selection_cancel_and_result_coverage`; `test_atomic_conflicts_and_replays_through_real_boundaries`; `test_probe_private_sentinel_never_read`; `test_offline_is_labelled_and_cannot_claim_real_quality`; `test_unavailable_is_pending_not_pass`; `test_wrong_interpretation_cannot_pass_by_safe_fallback`.
- [ ] **Step 2:** Run `python -m pytest tests/test_agent_end_to_end.py tests/test_agent_probe.py -q`; exigir RED.
- [ ] **Step 3 — GREEN:** Probe ejecuta matriz de spec §8, incluyendo captura de arroz+carne y «que lista tengo», varios productos con cantidades, negativas/condiciones, variantes/marca/talla/gramos, duplicados internos/existentes, incrementos conocidos/desconocidos, sustitución, preguntas intercaladas, edición tras resumen, TTL, fila reservada/cambiada y reinicio/replay. Guardar por paso texto, tool_calls/argumentos, estado/filas antes/después, reply y oracle; validar acción, cantidades, permisos y hechos por separado. Hash de skills/esquemas/prompts y modelo/parámetros en metadata. Simulados prueban fronteras, no comprensión.
- [ ] **Step 4:** Full suite `python -m pytest -q`, `python -m ruff check .`, `git diff --check`; todos deben pasar. Revisar cambios de tests legacy: solo versión de esquema cambia, no borrar expectativas de seguridad para lograr verde.
- [ ] **Step 5:** Ejecutar `python -P scripts/probe_skills_agent.py --output <ruta-evidencia-en-worktree>` usando PYTHONPATH explícito de worktree y Python de venv existente. Solo sintéticos; ningún reinicio ni Telegram. Repetir matriz real una segunda vez para identificar variabilidad; informar latencia fría/caliente observada, no prometer porcentaje global. Cualquier condición ignorada, herramienta incorrecta, éxito falso o fallo de selección => FAIL, no desplegar; depurar dentro del alcance aprobado sin añadir catálogo de frases.
- [ ] **Step 6:** Registrar resultados reales/offline por separado y limitaciones. Commit `test: verify skills agent confirmations and real E4B flows`. Revisión independiente de rama según método elegido, corregir hallazgos y reverificar antes de declarar listo.

## Self-review y cobertura

- Spec §§1–3: T1/T4/T5 y procedencia MIT; §§4–5: T2/T3/T6; §6: T2/T4/T5; §7: T3/T6; §8: T7.
- Tipos/firmas compartidos se definen en T1; operaciones/control no aceptan permisos del modelo. Migration conserva datos, cambio de ruta revoca solo memoria incompatible.
- Review Focus 1→T2/T6, 2→T3, 3→T2/T3, 4→T4/T5, 5→T3/T6.
- No se añade tarea de activación, merge, push, Telegram o limpieza privada. Tras aceptación, solicitar autorización separada.

## Puerta de ejecución

Plan pendiente de revisión del usuario y elección de método: subagent-driven (implementador/revisor por tarea) o nativo (implementación aquí y revisión independiente final). Recomendación: subagent-driven por interfaces de confirmación/persistencia y coste de un cambio de lista equivocado. No comenzar producto hasta esa respuesta.
