"""Pure pending-addition transitions; quantities never create incomplete rows."""

from datetime import datetime

from dialogue import (
    DIALOGUE_TTL,
    DialogueAnswer,
    DialogueDecision,
    DialogueMutation,
    DialogueState,
    LineRef,
    canonical_name,
)
from domain import ListLine


def begin_addition(state: DialogueState, lines: list[ListLine], *, now: datetime) -> DialogueDecision:
    if state.focus is None or state.focus.line is not None or state.target is not None:
        raise ValueError("Addition requires an unsaved product focus")
    matches = tuple(LineRef(id=l.id, revision=l.revision) for l in lines
                    if canonical_name(l.description) == canonical_name(state.focus.description))
    changes = {"pending_kind": "add", "updated_at": now, "expires_at": now + DIALOGUE_TTL}
    if matches and (not state.duplicate_confirmed or matches != state.candidates):
        state = state.model_copy(update={**changes, "question": "duplicate_choice",
            "options": ("change_quantity", "add"), "candidates": matches, "duplicate_confirmed": False})
        return DialogueDecision(mutation=None, legacy_intent=None, state=state, reply_kind="clarify")
    state = state.model_copy(update={**changes, "question": "add_quantity" if state.proposal_quantity is None else None,
                                   "options": (), "candidates": matches})
    if state.proposal_quantity is None:
        return DialogueDecision(mutation=None, legacy_intent=None, state=state,
            reply_kind="pending_add", prompt=f"¿Cuántos {state.focus.unit} de {state.focus.description} quieres añadir? Todavía no está en la lista.")
    return DialogueDecision(mutation=DialogueMutation(kind="add", description=state.focus.description,
        quantity=state.proposal_quantity, unit=state.focus.unit), legacy_intent=None, state=state, reply_kind="added")


def answer_addition(answer: DialogueAnswer, state: DialogueState,
                    lines: list[ListLine], *, now: datetime) -> DialogueDecision:
    if answer.kind == "cancel":
        return DialogueDecision(mutation=None, legacy_intent=None, state=None, reply_kind="cancelled",
                                presentation_reason="cancelled_pending", prompt="Propuesta cancelada.")
    if (answer.kind == "quantity" and state.question == "add_quantity"
            and answer.quantity is not None):
        state = state.model_copy(update={"proposal_quantity": answer.quantity,
            "focus": state.focus.model_copy(update={"unit": answer.unit or state.focus.unit})})
    elif answer.kind == "add" and state.question in {"duplicate_choice", "add_or_replace"}:
        state = state.model_copy(update={"target": None,
            "duplicate_confirmed": state.question == "duplicate_choice"})
    else:
        return DialogueDecision(mutation=None, legacy_intent=None, state=state, reply_kind="clarify")
    return begin_addition(state, lines, now=now)
