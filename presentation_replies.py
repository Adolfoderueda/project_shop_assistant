"""Build grounded presentation from typed transaction results, never parsed prose."""

from dialogue import DialogueDecision, DialogueState
from domain import ListLine, Reply
from presentation import PresentationFact, PresentationOption, PresentationSnapshot
from product_memory import ObservedProduct, identifiable_product_name

REASONS = {
    "generic": "Aclara el producto o la acción concreta. No he cambiado la lista.",
    "expired": "La propuesta ha caducado. Indica de nuevo el producto y la acción.",
    "stale": "La lista ha cambiado. Revisa el producto y vuelve a indicarlo.",
    "reserved": "La entrada está reservada. Revisa la lista; no he cambiado esa entrada.",
    "quantity_range": "Indica una cantidad entera de envases dentro del rango permitido.",
    "diaper_unit": "Indica paquetes o envases de pañales explícitamente.",
    "no_pending": "No hay propuesta pendiente. No he cambiado la lista.",
    "cancelled_pending": "Propuesta cancelada; no he deshecho entradas ya guardadas.",
}


def quantity_text(quantity: int | None, unit: str = "envases") -> str:
    if quantity is None:
        return "cantidad pendiente"
    return f"{quantity} {unit[:-1] if quantity == 1 else unit}"


def _question(state: DialogueState, lines: list[ListLine]) -> tuple[str, list[str]]:
    name = state.focus.description if state.focus else "el producto"
    unit = state.focus.unit if state.focus else "envases"
    source = next((l for l in lines if state.target and l.id == state.target.id
                   and l.revision == state.target.revision), None)
    source_name = source.description if source else "el producto de origen"
    q = state.question
    options = []
    if q in {"quantity", "replace_quantity"}:
        question = f"Indica la cantidad total de {unit} para {name}, no un incremento."
        if q == "replace_quantity" and source and source.quantity is not None:
            options.append(f"Conserva la cantidad: responde «conserva la cantidad» ({quantity_text(source.quantity, unit)}).")
    elif q == "duplicate_choice":
        question = f"Ya tienes entradas de {name}. ¿Quieres cambiar la cantidad total o añadir otra entrada?"
        labels = {"change_quantity": "Cambiar cantidad total", "add": "Añadir otra entrada"}
        options.extend(f"{i}: {labels[action]}" for i, action in enumerate(state.options, 1))
    elif q == "add_or_replace":
        question = f"¿Quieres añadir {name} o sustituir {source_name} por {name}?" if source else f"¿Quieres añadir {name}?"
        labels = {"add": f"Añadir {name} (añádelo)", "replace": f"Sustituir {source_name} por {name} (sustitúyelo)"}
        options.extend(f"{i}: {labels[action]}" for i, action in enumerate(state.options, 1))
    elif q == "select_line":
        question = "Selecciona una entrada por su número."
        options.extend(f"{i}: Entrada {i}" for i, _ in enumerate(state.candidates, 1))
    elif q == "confirm_replace":
        question = f"¿Confirmas sustituir {source_name} por {name}? Todavía no lo he sustituido."
        options.append("Sí: confirma la sustitución.")
    elif q == "replace_duplicate":
        question = (f"Ya tienes {name}. ¿Confirmas sustituir {source_name} por {name} con "
                    f"{quantity_text(state.proposal_quantity, unit)} y mantener entradas separadas? "
                    "No se sumarán ni fusionarán; todavía no lo he sustituido.")
        options.append("Sí: confirma mantener entradas separadas.")
    else:
        question = "Para quitar una entrada, envía su ID exacto o /quitar <id>."
        # Ordinals are presentation labels only: the parser still requires IDs.
        options.extend(f"Entrada {i}: usa el ID indicado por la aplicación."
                       for i, _ in enumerate(state.candidates, 1))
    options.append("Cancelar: responde «cancelar».")
    return question, options


def build_presentation(
    decision: DialogueDecision, affected: ListLine | None, lines: list[ListLine],
    legacy_reply: Reply | None, *, observations: list[ObservedProduct], original: ListLine | None,
) -> PresentationSnapshot:
    facts: list[str] = []
    options: list[str] = []
    question = None
    kind = "clarify"
    state = decision.state
    unit = state.focus.unit if state and state.focus else "envases"
    if affected is not None and decision.reply_kind in {"added", "updated", "replaced"}:
        kind = decision.reply_kind
        details = f"{affected.description}: {quantity_text(affected.quantity, unit)}."
        if kind == "replaced":
            if original is None:
                raise ValueError("Replacement presentation requires the original saved row")
            facts.append(f"He sustituido {original.description} por {details}")
        elif kind == "added":
            facts.append(f"He añadido {details}")
        else:
            facts.append(f"He actualizado la cantidad total de {details}")
    elif decision.reply_kind == "natural_list" or (
        decision.legacy_intent and decision.legacy_intent.action == "list"
    ):
        kind = "list"
        facts.extend(f"Entrada {i}: {l.description}: {quantity_text(l.quantity)}."
                     for i, l in enumerate(lines, 1))
        if not facts:
            facts.append("La lista está vacía.")
    elif decision.legacy_intent and decision.legacy_intent.action == "product_query":
        kind = "product"
        intent = decision.legacy_intent
        valid = (len(intent.lines) == 1 and intent.lines[0].description
                 and identifiable_product_name(intent.lines[0].description)
                 and intent.lines[0].line_id is None and intent.lines[0].quantity is None
                 and intent.lines[0].url is None)
        if not valid:
            facts.append("Aclara el producto que buscas.")
        elif observations:
            for p in observations:
                price = (f"{p.price_cents // 100},{p.price_cents % 100:02d} €"
                         if p.price_cents is not None else "no observado")
                stock = ("no observado" if p.availability is None else
                         "disponible" if p.availability else "no disponible")
                facts.append(f"{p.title} — fuente {p.store_id} ({p.url}); observado {p.observed_on}; "
                             f"precio observado {price}; stock observado {stock}; "
                             f"{p.format_note or 'sin detalle de formato'}. Datos históricos: precio y stock no actuales.")
        else:
            facts.append(f"No tenemos ficha observada de {intent.lines[0].description}.")
            # A supplied legacy result certifies _apply completed; its text is opaque.
            if legacy_reply is not None:
                facts.append("Lo he anotado para revisar.")
    elif decision.reply_kind == "cancelled":
        kind = "cancelled"
        facts.append(REASONS[decision.presentation_reason])

    if state and state.question and decision.presentation_reason == "generic":
        if kind == "clarify":
            kind = "question"
        if state.question in {"duplicate_choice", "select_line", "remove_id", "replace_duplicate"}:
            rows = {l.id: l for l in lines}
            for i, reference in enumerate(state.candidates, 1):
                row = rows.get(reference.id)
                if row and row.revision == reference.revision:
                    facts.append(f"Entrada {i}: {row.description}: {quantity_text(row.quantity)}.")
        question, options = _question(state, lines)
    if not facts and question is None:
        facts.append(REASONS[decision.presentation_reason])
    text = "\n".join([*facts, *([question] if question else []), *options])
    if state and state.question == "remove_id" and question is not None:
        text += "\n" + "\n".join(f"Entrada {i}: /quitar {r.id}"
                                  for i, r in enumerate(state.candidates, 1))
    # Technical/command results retain essential IDs and all legacy scalar metadata.
    fallback = legacy_reply if decision.reply_kind == "legacy" and kind != "product" and legacy_reply else Reply(text=text)
    result = PresentationSnapshot(version=1, kind=kind,
        facts=tuple(PresentationFact(key=f"f{i}", text=t) for i, t in enumerate(facts)),
        options=tuple(PresentationOption(key=f"o{i}", text=t) for i, t in enumerate(options)),
        question=question, fallback=fallback)
    return PresentationSnapshot.model_validate_json(result.model_dump_json())


def fallback_reply(snapshot: PresentationSnapshot) -> Reply:
    return PresentationSnapshot.model_validate_json(snapshot.model_dump_json()).fallback
