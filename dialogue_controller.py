"""Pure transitions: proposals never carry mutation authority."""

import re
from datetime import datetime

from dialogue import (
    DIALOGUE_TTL,
    MAX_QUANTITY,
    DialogueAnswer,
    DialogueDecision,
    DialogueMutation,
    DialogueState,
    LineRef,
    ProductMention,
    canonical_name,
    expired,
    parse_answer,
)
from dialogue_additions import answer_addition, begin_addition
from dialogue_increments import answer_increment, begin_increment
from dialogue_requests import classify_request, validate_request
from dialogue_requests import literal_request as _literal_request
from dialogue_requests import product_name as _product_name
from domain import IncomingMessage, Intent, IntentLine, ListLine, utc
from interpreter import diaper_reference, explicit_diaper_packs, parse_command

CONTEXT_ALIASES = {"anade eso", "anadelo", "anadelo a mi lista"}


def closed_attempt(text: str) -> bool:
    """Even incompatible closed replies need clarification, not a model call."""
    clean = canonical_name(text)
    return clean in CONTEXT_ALIASES | {
        "si", "no", "confirmo", "cancelar", "sustituyelo", "cambiar cantidad",
        "anadir otra linea", "conserva la cantidad",
    } or re.fullmatch(r"[1-9][0-9]*(?: (?:envases|paquetes|botes|sacos))?", clean) is not None


def literal_request(text: str) -> tuple[str, str] | None:
    return _literal_request(text)


def product_name(text: str) -> str | None:
    return _product_name(text)


def validate_model(text: str, intent: Intent, lines: list[ListLine]) -> Intent:
    return validate_request(text, intent, lines)


def ref(line: ListLine) -> LineRef:
    return LineRef(id=line.id, revision=line.revision)


def question_prompt(state: DialogueState, lines: list[ListLine]) -> str:
    name = state.focus.description if state.focus else "el producto"
    if state.question == "add_quantity":
        return f"¿Cuántos {state.focus.unit} de {name} quieres añadir? Todavía no está en la lista."
    if state.question == "increment_quantity":
        return f"¿Cuántos {state.focus.unit} adicionales de {name} quieres añadir?"
    if state.question == "confirm_increment":
        return (f"¿Confirmas añadir {state.additional_quantity} {state.focus.unit} a {name}? "
                f"Pasaría de {state.base_quantity} a {state.proposal_quantity} {state.focus.unit}. Sí o no.")
    if state.question in {"increment_missing", "increment_unknown"}:
        reason = (f"No hay una entrada guardada de {name}." if state.question == "increment_missing"
                  else f"La cantidad guardada de {name} es desconocida; no se puede incrementar.")
        labels = {"add": "añadir otra línea", "change_quantity": "cambiar cantidad (total)"}
        return reason + " " + "; ".join(f"{i}: {labels[key]}" for i, key in enumerate(state.options, 1)) + ". O cancelar."
    if state.question == "quantity":
        return f"Indica la cantidad de {state.focus.unit} para {name}."
    if state.question == "duplicate_choice":
        quantities = ", ".join(
            f"{l.quantity or '?'} envases" for l in lines if ref(l) in state.candidates
        )
        return f"Ya tienes {name}: {quantities}. 1: cambiar cantidad (total); 2: añadir otra línea."
    if state.question == "add_or_replace":
        source = next((l.description for l in lines if ref(l) == state.target), None)
        return (f"¿Quieres 1: añadir {name} o 2: sustituir {source} por {name}?" if source
                else f"¿Quieres añadir {name}? 1: añadir.")
    if state.question == "select_line":
        rows = {l.id: l for l in lines}
        return "Selecciona una línea: " + "; ".join(
            f"{i}: {rows[r.id].description}: {rows[r.id].quantity or '?'} envases"
            for i, r in enumerate(state.candidates, 1) if r.id in rows
        )
    if state.question == "confirm_replace":
        source = next((l.description for l in lines if ref(l) == state.target), "el origen")
        return f"¿Confirmas sustituir {source} por {name}?"
    if state.question == "replace_quantity":
        source = next((l for l in lines if ref(l) == state.target), None)
        keep = (f" Puedes responder «conserva la cantidad» ({source.quantity} {state.focus.unit})"
                " o indicar otra." if source and source.quantity is not None else "")
        return f"Indica la cantidad de {state.focus.unit} para {name}." + keep
    if state.question == "replace_duplicate":
        return (f"Ya tienes {name}. ¿Confirmas mantener líneas separadas con "
                f"{state.proposal_quantity} {state.focus.unit} en la línea sustituida? "
                "No se sumarán ni fusionarán; responde sí o cancelar.")
    if state.question == "remove_id":
        return "Indica el ID exacto con /quitar <id>: " + ", ".join(r.id for r in state.candidates)
    return f"Aclara la propuesta para {name}."


def reduce_dialogue(
    message: IncomingMessage, proposal: Intent | None, state: DialogueState | None,
    lines: list[ListLine], reserved_ids: frozenset[str], *, now: datetime,
) -> DialogueDecision:
    utc(now)
    was_expired = state is not None and expired(state, now)
    if state and (expired(state, now) or (state.user_id, state.chat_id) != (message.user_id, message.chat_id)):
        state = None
    rows = {l.id: l for l in lines}
    references = (() if not state else (*state.candidates, *([state.target] if state.target else []),
                  *([state.focus.line] if state.focus and state.focus.line else [])))
    stale = any(r.id not in rows or ref(rows[r.id]) != r for r in references)
    if state and state.pending_kind == "increment" and state.target and not stale:
        current = rows[state.target.id]
        stale = (current.quantity != state.base_quantity
                 or canonical_name(current.description) != canonical_name(state.focus.description))
    reserved_increment = bool(state and state.pending_kind == "increment" and state.target
                              and state.target.id in reserved_ids)
    if stale or reserved_increment:
        state = None

    def decision(kind="clarify", *, mutation=None, legacy=None, prompt=None, reason="generic"):
        return DialogueDecision(mutation=mutation, legacy_intent=legacy, state=state,
                                reply_kind=kind, prompt=prompt, presentation_reason=reason)

    def renew(**changes):
        nonlocal state
        state = state.model_copy(update={**changes, "updated_at": now, "expires_at": now + DIALOGUE_TTL})

    def fresh(focus, **kwargs):
        nonlocal state
        state = DialogueState(user_id=message.user_id, chat_id=message.chat_id, focus=focus,
                              updated_at=now, expires_at=now + DIALOGUE_TTL, **kwargs)

    def add_focus():
        nonlocal state
        state = state.model_copy(update={"target": None})
        result = begin_addition(state, lines, now=now)
        return result.model_copy(update={"prompt": question_prompt(result.state, lines)
                                       if result.state.question else None})

    def replace_focus():
        matches = tuple(ref(l) for l in lines if l.id != state.target.id
                        and canonical_name(l.description) == canonical_name(state.focus.description))
        if matches and (not state.duplicate_confirmed or matches != state.candidates):
            renew(question="replace_duplicate", candidates=matches, options=(), duplicate_confirmed=False)
            return decision(prompt=question_prompt(state, lines))
        renew(question=None, options=(), candidates=matches)
        return decision("replaced", mutation=DialogueMutation(
            kind="replace", target=state.target, description=state.focus.description,
            quantity=state.proposal_quantity, unit=state.focus.unit,
        ))

    clean = canonical_name(message.text)
    request = classify_request(message.text)
    # Source grammar, not a model action or the legacy add parser, authorizes this branch.
    if request is not None and request.action == "increment":
        result = begin_increment(ProductMention(description=request.description,
            source_update_id=message.update_id), lines, reserved_ids,
            user_id=message.user_id, chat_id=message.chat_id, now=now)
        return result.model_copy(update={"prompt": question_prompt(result.state, lines)
                                       if result.state and result.state.question else result.prompt})
    command = parse_command(message.text, lines)
    intent = command if command is not None else proposal
    if command is None and intent is not None:
        intent = validate_model(message.text, intent, lines)
    if intent is not None and any(
        line.quantity is not None and line.quantity > MAX_QUANTITY for line in intent.lines
    ):
        return decision(prompt="Indica una cantidad entera de envases dentro del rango permitido.",
                        reason="quantity_range")
    priority = message.text.strip().startswith("/") or (command and command.action == "buy")
    answer = None if priority else parse_answer(message.text, state, now=now)
    if answer and answer.kind == "cancel":
        had_state = state is not None
        state = None
        return decision("cancelled", prompt=("Propuesta cancelada; no he deshecho líneas ya guardadas."
                        if had_state else "No hay propuesta pendiente."),
                        reason="cancelled_pending" if had_state else "no_pending")
    if stale and not priority and (intent is None or intent.action == "clarify"):
        return decision(prompt="La lista ha cambiado; revisa el producto y vuelve a indicarlo.",
                        reason="stale")
    if reserved_increment and not priority and (intent is None or intent.action == "clarify"):
        return decision(prompt="La línea está reservada; revisa la lista.", reason="reserved")
    if answer and state:
        if answer.kind == "select" and state.question != "select_line":
            answer = DialogueAnswer(kind=state.options[answer.selection - 1])
        if state.pending_kind == "increment":
            if (answer.kind == "quantity" and diaper_reference(state.focus.description)
                    and not explicit_diaper_packs(message.text)):
                return decision(prompt="Indica paquetes/envases de pañales explícitamente.", reason="diaper_unit")
            result = answer_increment(answer, state, lines, reserved_ids, now=now)
            return result.model_copy(update={"prompt": question_prompt(result.state, lines)
                if result.state and result.state.question and result.presentation_reason == "generic"
                else result.prompt})
        if (state.target and state.target.id in reserved_ids
                and state.question in {"add_or_replace", "confirm_replace", "replace_quantity", "replace_duplicate"}
                and answer.kind != "add"):
            state = None
            return decision(prompt="La línea está reservada; revisa la lista.", reason="reserved")
        if answer.kind == "add" and state.focus:
            if state.question == "duplicate_choice":
                renew(duplicate_confirmed=True)
            return add_focus()
        if answer.kind == "quantity" and state.question == "add_quantity":
            if diaper_reference(state.focus.description) and not explicit_diaper_packs(message.text):
                return decision(prompt="Indica paquetes/envases de pañales explícitamente.", reason="diaper_unit")
            result = answer_addition(answer, state, lines, now=now)
            return result.model_copy(update={"prompt": question_prompt(result.state, lines)
                                           if result.state.question else None})
        if answer.kind == "change_quantity":
            if len(state.candidates) > 1:
                renew(question="select_line", options=("change_quantity",), pending_kind=None)
            else:
                target = state.candidates[0]
                renew(question="quantity", target=target, candidates=(), options=(),
                      pending_kind=None, duplicate_confirmed=False, proposal_quantity=None,
                      focus=state.focus.model_copy(update={"line": target}))
            return decision(prompt=question_prompt(state, lines))
        if answer.kind == "select" and state.question == "select_line":
            target = state.candidates[answer.selection - 1]
            renew(question="quantity", target=target, candidates=(), options=(),
                  pending_kind=None, duplicate_confirmed=False, proposal_quantity=None,
                  focus=state.focus.model_copy(update={"line": target}))
            return decision(prompt=question_prompt(state, lines))
        if answer.kind == "quantity" and state.question == "quantity" and state.target:
            if state.target.id in reserved_ids:
                state = None
                return decision(prompt="La línea está reservada; revisa la lista.", reason="reserved")
            if diaper_reference(state.focus.description) and not explicit_diaper_packs(message.text):
                return decision(prompt="Indica paquetes/envases de pañales explícitamente.", reason="diaper_unit")
            unit = answer.unit or state.focus.unit
            renew(question=None, focus=state.focus.model_copy(update={"unit": unit}),
                  candidates=(), options=(), proposal_quantity=None)
            return decision("updated", mutation=DialogueMutation(kind="set_quantity", target=state.target,
                            quantity=answer.quantity, unit=unit))
        if answer.kind == "remove_id":
            state = None
            return decision("legacy", legacy=Intent(action="remove", lines=[IntentLine(line_id=answer.line_id)]))
        if answer.kind == "replace" and state.target:
            renew(question="confirm_replace", options=())
            return decision(prompt=question_prompt(state, lines))
        if answer.kind == "confirm" and state.question == "confirm_replace" and state.target and state.focus:
            renew(question="replace_quantity", replacement_confirmed=True, proposal_quantity=None,
                  duplicate_confirmed=False, candidates=(), options=())
            return decision(prompt=question_prompt(state, lines))
        if (answer.kind in {"quantity", "keep_quantity"} and state.question == "replace_quantity"
                and state.target and state.focus and state.replacement_confirmed):
            quantity = rows[state.target.id].quantity if answer.kind == "keep_quantity" else answer.quantity
            if quantity is None:
                return decision(prompt=question_prompt(state, lines))
            if diaper_reference(state.focus.description) and not explicit_diaper_packs(message.text):
                return decision(prompt="Indica paquetes/envases de pañales explícitamente.", reason="diaper_unit")
            renew(proposal_quantity=quantity, focus=state.focus.model_copy(update={
                "unit": answer.unit or state.focus.unit,
            }))
            return replace_focus()
        if (answer.kind == "confirm" and state.question == "replace_duplicate"
                and state.target and state.focus and state.replacement_confirmed and state.proposal_quantity):
            renew(duplicate_confirmed=True)
            return replace_focus()
        return decision(prompt=question_prompt(state, lines))
    if clean in CONTEXT_ALIASES:
        return decision(prompt="Indica el producto y la acción explícitamente." if not state else question_prompt(state, lines),
                        reason="expired" if was_expired else "generic")
    if intent is None or intent.action == "clarify":
        if command and command.question and "dentro del rango permitido" in command.question:
            return decision(prompt=command.question, reason="quantity_range")
        if command and command.lines:
            fresh(None, question="remove_id", candidates=tuple(ref(rows[l.line_id]) for l in command.lines))
        return decision(prompt=question_prompt(state, lines) if state and state.question else
                        (intent.question if command and intent else "Aclara el producto o la acción concreta."),
                        reason="expired" if was_expired else "generic")
    if intent.action == "list":
        return decision("legacy" if clean == "/lista" else "natural_list",
                        legacy=intent if clean == "/lista" else None)
    if intent.action == "greet":
        return decision("greeting", prompt="¡Hola! ¿Qué necesitas para tu lista?")
    if command and intent.action == "set_quantity":
        target = rows.get(intent.lines[0].line_id)
        if target is None:
            return decision(prompt="Indica un ID existente de /lista.")
        fresh(ProductMention(description=target.description, source_update_id=message.update_id,
                             line=ref(target)))
        return decision("updated", mutation=DialogueMutation(kind="set_quantity", target=ref(target),
                        quantity=intent.lines[0].quantity))
    if intent.action in {"add", "mention_product", "product_query"}:
        line = intent.lines[0]
        focus = ProductMention(description=line.description, source_update_id=message.update_id)
        if command and intent.action == "add":
            unit = re.search(r"\b(paquetes?|envases?|botes?|sacos?)\b", canonical_name(message.text))
            if unit:
                label = unit[1] if unit[1].endswith("s") else unit[1] + "s"
                focus = focus.model_copy(update={"unit": label})
        old_target = state.focus.line if state and state.focus else None
        if intent.action == "product_query":
            if not state or (state.pending_kind is None and state.question is None):
                fresh(focus)
            return decision("legacy", legacy=intent)
        if intent.action == "mention_product":
            fresh(focus, question="add_or_replace", target=old_target,
                  options=("add", "replace") if old_target else ("add",))
            return decision(prompt=question_prompt(state, lines))
        fresh(focus, proposal_quantity=line.quantity)
        return add_focus()
    if intent.action == "buy":
        missing = next((l for l in lines if l.quantity is None), None)
        if missing:
            fresh(ProductMention(description=missing.description, source_update_id=message.update_id,
                                 line=ref(missing)), target=ref(missing), question="quantity")
            return decision(prompt=question_prompt(state, lines))
    state = None
    return decision("legacy", legacy=intent)
