"""Pure selected-increment transitions; never execute a model proposal."""

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
)
from dialogue_additions import begin_addition
from domain import ListLine


def _decision(state, *, mutation=None, kind="clarify", reason="generic", prompt=None):
    return DialogueDecision(state=state, mutation=mutation, legacy_intent=None,
                            reply_kind=kind, presentation_reason=reason, prompt=prompt)


def _renew(state, now, **changes):
    return state.model_copy(update={**changes, "updated_at": now,
                                   "expires_at": now + DIALOGUE_TTL})


def _selected(state, line, reserved_ids, now):
    if line.id in reserved_ids:
        return _decision(None, reason="reserved", prompt="La línea está reservada; revisa la lista.")
    target = LineRef(id=line.id, revision=line.revision)
    return _decision(_renew(state, now, target=target, candidates=(),
        focus=state.focus.model_copy(update={"line": target}), base_quantity=line.quantity,
        question="increment_unknown" if line.quantity is None else "increment_quantity",
        options=("change_quantity", "add") if line.quantity is None else ()))


def begin_increment(focus: ProductMention, lines: list[ListLine], reserved_ids: frozenset[str],
                    *, user_id: int, chat_id: int, now: datetime) -> DialogueDecision:
    matches = [l for l in lines if canonical_name(l.description) == canonical_name(focus.description)]
    state = DialogueState(user_id=user_id, chat_id=chat_id, focus=focus,
                          pending_kind="increment", updated_at=now, expires_at=now + DIALOGUE_TTL)
    if not matches:
        return _decision(state.model_copy(update={"question": "increment_missing", "options": ("add",)}))
    if len(matches) > 1:
        return _decision(state.model_copy(update={"question": "select_line",
            "candidates": tuple(LineRef(id=l.id, revision=l.revision) for l in matches)}))
    return _selected(state, matches[0], reserved_ids, now)


def answer_increment(answer: DialogueAnswer, state: DialogueState, lines: list[ListLine],
                     reserved_ids: frozenset[str], *, now: datetime) -> DialogueDecision:
    """Consume only closed answers after the controller revalidates references."""
    if answer.kind in {"cancel", "reject"}:
        return _decision(None, kind="cancelled", reason="cancelled_pending",
                         prompt="Incremento cancelado; no he cambiado la lista.")
    if answer.kind == "select" and state.question == "select_line":
        if answer.selection is None or not 1 <= answer.selection <= len(state.candidates):
            return _decision(state)
        target = state.candidates[answer.selection - 1]
        line = next((l for l in lines if LineRef(id=l.id, revision=l.revision) == target), None)
        if line is None:
            return _decision(None, reason="stale", prompt="La lista ha cambiado; revisa el producto.")
        return _selected(state, line, reserved_ids, now)
    if answer.kind == "add" and state.question in {"increment_missing", "increment_unknown"}:
        fresh = _renew(state, now, pending_kind=None, target=None, candidates=(), question=None,
            options=(), base_quantity=None, additional_quantity=None, proposal_quantity=None,
            increment_confirmed=False, focus=state.focus.model_copy(update={"line": None}))
        return begin_addition(fresh, lines, now=now)
    if answer.kind == "change_quantity" and state.question == "increment_unknown":
        return _decision(_renew(state, now, pending_kind=None, question="quantity", options=(),
            base_quantity=None, additional_quantity=None, proposal_quantity=None, increment_confirmed=False))
    if answer.kind == "quantity" and state.question == "increment_quantity" and answer.quantity is not None:
        total = state.base_quantity + answer.quantity
        if total > MAX_QUANTITY:
            return _decision(state, reason="quantity_range",
                             prompt="Indica una cantidad entera de envases dentro del rango permitido.")
        return _decision(_renew(state, now, question="confirm_increment",
            additional_quantity=answer.quantity, proposal_quantity=total,
            focus=state.focus.model_copy(update={"unit": answer.unit or state.focus.unit})))
    if answer.kind == "confirm" and state.question == "confirm_increment":
        final = _renew(state, now, question=None, increment_confirmed=True)
        return _decision(final, kind="incremented", mutation=DialogueMutation(
            kind="increment", target=state.target, description=state.focus.description,
            expected_base=state.base_quantity, additional_quantity=state.additional_quantity,
            quantity=state.proposal_quantity, unit=state.focus.unit))
    return _decision(state)
