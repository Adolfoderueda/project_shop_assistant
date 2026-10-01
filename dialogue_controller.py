"""Pure transitions: proposals never carry mutation authority."""

import re
from datetime import datetime

from dialogue import (
    DIALOGUE_TTL,
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
from domain import IncomingMessage, Intent, IntentLine, ListLine, utc
from interpreter import clarify, diaper_reference, explicit_diaper_packs, normalized, parse_command
from product_memory import identifiable_product_name

CONTEXT_ALIASES = {"anade eso", "anadelo", "anadelo a mi lista"}


def closed_attempt(text: str) -> bool:
    """Even incompatible closed replies need clarification, not a model call."""
    clean = canonical_name(text)
    return clean in CONTEXT_ALIASES | {
        "si", "no", "confirmo", "cancelar", "sustituyelo", "cambiar cantidad",
        "anadir otra linea", "conserva la cantidad",
    } or re.fullmatch(r"[1-9][0-9]*(?: (?:envases|paquetes|botes|sacos))?", clean) is not None


def product_name(text: str) -> str | None:
    clean = normalized(text).strip().removeprefix("¿").removesuffix("?").strip()
    match = re.fullmatch(r"(?:que sabes de (.+)|que (.+) vimos|tenemos ficha de (.+))", clean)
    if not match:
        return None
    name = next(group for group in match.groups() if group is not None).strip()
    if (not identifiable_product_name(name)
            or re.search(r'\b(?:no|nunca|si|o|u|y|cuando)\b|[?¿!¡.,;:"«»“”<>/\\]|https?\b|\n', name)
            or re.search(r"\b\d+\s+(?:paquetes?|botes?|sacos?|envases?|unidades?)\b", name)):
        return None
    return name


def literal_request(text: str) -> tuple[str, str] | None:
    """Recognize the existing whole-message grammar, retaining original product data."""
    match = re.fullmatch(r"(ahora|necesito|quiero|me hace falta|me hacen falta)\s+(.+)", normalized(text))
    if not match:
        return None
    requested = match[2].removesuffix(" por favor")
    if re.search(
        r'\b(no|nunca|si|o|u|y|cuando|gracias)\b|\b(?:en caso de|a menos que|por favor)\b|[?¿!¡.,;:"«»“”<>\\]|https?\b|\n',
        requested,
    ):
        return None
    without_qualifiers = re.sub(r"\b(?:tipo|talla|etapa)\s+[1-9]\d*\b", "", requested)
    if re.search(r"\d", without_qualifiers):
        return None
    # Split only the recognized prefix, never normalize/reconstruct the product name.
    original = text.strip().split(maxsplit=len(match[1].split()))[-1]
    if match[2].endswith(" por favor"):
        original = original.rsplit(" ", 2)[0]
    return ("mention_product" if match[1] == "ahora" else "add", original)


def validate_model(text: str, intent: Intent, lines: list[ListLine]) -> Intent:
    if intent.action in {"buy", "resume", "remove", "set_quantity", "status"}:
        return clarify("Usa un comando explícito para esa operación.")
    if intent.action in {"add", "mention_product"}:
        request = literal_request(text)
        if request is None or intent.action != request[0]:
            return clarify()
        if len(intent.lines) != 1 or intent.order_id is not None or intent.question is not None:
            return clarify()
        line = intent.lines[0]
        if not line.description or canonical_name(line.description) != canonical_name(request[1]):
            return clarify("No puedo omitir características del producto.")
        if line.line_id is not None or line.quantity is not None or line.url is not None:
            return clarify()
    if intent.action == "product_query":
        requested = product_name(text)
        if (requested is None or len(intent.lines) != 1 or intent.order_id is not None
                or intent.question is not None or intent.lines[0].line_id is not None
                or intent.lines[0].quantity is not None or intent.lines[0].url is not None
                or not intent.lines[0].description
                or canonical_name(intent.lines[0].description) != canonical_name(requested)):
            return clarify("Aclara el producto con una pregunta completa.")
    if intent.action == "clarify":
        return clarify("Aclara el producto o la acción.")
    return intent


def ref(line: ListLine) -> LineRef:
    return LineRef(id=line.id, revision=line.revision)


def question_prompt(state: DialogueState, lines: list[ListLine]) -> str:
    name = state.focus.description if state.focus else "el producto"
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
    if state and (expired(state, now) or (state.user_id, state.chat_id) != (message.user_id, message.chat_id)):
        state = None
    rows = {l.id: l for l in lines}
    references = (() if not state else (*state.candidates, *([state.target] if state.target else []),
                  *([state.focus.line] if state.focus and state.focus.line else [])))
    stale = any(r.id not in rows or ref(rows[r.id]) != r for r in references)
    if stale:
        state = None

    def decision(kind="clarify", *, mutation=None, legacy=None, prompt=None):
        return DialogueDecision(mutation=mutation, legacy_intent=legacy, state=state,
                                reply_kind=kind, prompt=prompt)

    def renew(**changes):
        nonlocal state
        state = state.model_copy(update={**changes, "updated_at": now, "expires_at": now + DIALOGUE_TTL})

    def fresh(focus, **kwargs):
        nonlocal state
        state = DialogueState(user_id=message.user_id, chat_id=message.chat_id, focus=focus,
                              updated_at=now, expires_at=now + DIALOGUE_TTL, **kwargs)

    def add_focus():
        matches = [ref(l) for l in lines if canonical_name(l.description) == canonical_name(state.focus.description)]
        if matches and not state.duplicate_confirmed:
            renew(question="duplicate_choice", options=("change_quantity", "add"),
                  candidates=tuple(matches), target=None)
            return decision(prompt=question_prompt(state, lines))
        renew(question="quantity" if state.proposal_quantity is None else None,
              options=(), candidates=(), target=None)
        return decision("added", mutation=DialogueMutation(kind="add", description=state.focus.description,
                        quantity=state.proposal_quantity, unit=state.focus.unit))

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
    command = parse_command(message.text, lines)
    intent = command if command is not None else proposal
    if command is None and intent is not None:
        intent = validate_model(message.text, intent, lines)
    priority = message.text.strip().startswith("/") or (command and command.action == "buy")
    answer = None if priority else parse_answer(message.text, state, now=now)
    if answer and answer.kind == "cancel":
        had_state = state is not None
        state = None
        return decision("cancelled", prompt=("Propuesta cancelada; no he deshecho líneas ya guardadas."
                        if had_state else "No hay propuesta pendiente."))
    if stale and not priority and (intent is None or intent.action == "clarify"):
        return decision(prompt="La lista ha cambiado; revisa el producto y vuelve a indicarlo.")
    if answer and state:
        if answer.kind == "select" and state.question != "select_line":
            answer = DialogueAnswer(kind=state.options[answer.selection - 1])
        if (state.target and state.target.id in reserved_ids
                and state.question in {"add_or_replace", "confirm_replace", "replace_quantity", "replace_duplicate"}
                and answer.kind != "add"):
            state = None
            return decision(prompt="La línea está reservada; revisa la lista.")
        if answer.kind == "add" and state.focus:
            if state.question == "duplicate_choice":
                renew(duplicate_confirmed=True)
            return add_focus()
        if answer.kind == "change_quantity":
            if len(state.candidates) > 1:
                renew(question="select_line", options=("change_quantity",))
            else:
                target = state.candidates[0]
                renew(question="quantity", target=target, candidates=(), options=(),
                      focus=state.focus.model_copy(update={"line": target}))
            return decision(prompt=question_prompt(state, lines))
        if answer.kind == "select" and state.question == "select_line":
            target = state.candidates[answer.selection - 1]
            renew(question="quantity", target=target, candidates=(), options=(),
                  focus=state.focus.model_copy(update={"line": target}))
            return decision(prompt=question_prompt(state, lines))
        if answer.kind == "quantity" and state.question == "quantity" and state.target:
            if state.target.id in reserved_ids:
                state = None
                return decision(prompt="La línea está reservada; revisa la lista.")
            if diaper_reference(state.focus.description) and not explicit_diaper_packs(message.text):
                return decision(prompt="Indica paquetes/envases de pañales explícitamente.")
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
                return decision(prompt="Indica paquetes/envases de pañales explícitamente.")
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
        return decision(prompt="Indica el producto y la acción explícitamente." if not state else question_prompt(state, lines))
    if intent is None or intent.action == "clarify":
        if command and command.lines:
            fresh(None, question="remove_id", candidates=tuple(ref(rows[l.line_id]) for l in command.lines))
        return decision(prompt=question_prompt(state, lines) if state and state.question else
                        (intent.question if command and intent else "Aclara el producto o la acción concreta."))
    if intent.action == "list":
        return decision("legacy" if clean == "/lista" else "natural_list",
                        legacy=intent if clean == "/lista" else None)
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
