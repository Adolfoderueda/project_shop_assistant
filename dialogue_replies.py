"""Replies built from rows actually saved, not model-generated prose."""

from dialogue import DialogueDecision
from dialogue_controller import question_prompt
from domain import ListLine, Reply
from presentation_replies import build_presentation, quantity_text


def render_dialogue_result(
    decision: DialogueDecision, affected: ListLine | None, lines: list[ListLine],
    legacy_reply: Reply | None = None,
) -> Reply:
    if decision.reply_kind == "legacy":
        return legacy_reply or Reply(text="No he cambiado la lista.")
    if affected is None:
        if (decision.prompt and decision.reply_kind == "clarify"
                and not (decision.state and decision.state.question)):
            # Operational scalar prompts (e.g. explicit diaper units) are already
            # application-owned; do not erase them with the generic fallback.
            return Reply(text=decision.prompt)
        return build_presentation(decision, None, lines, legacy_reply,
                                  observations=[], original=None).fallback
    if affected and decision.reply_kind in {"added", "updated", "replaced", "incremented"}:
        unit = (decision.mutation.unit if decision.mutation else
                decision.state.focus.unit if decision.state and decision.state.focus else "envases")
        text = (f"He añadido {affected.description}." if decision.reply_kind == "added"
                else f"{affected.description}: {quantity_text(affected.quantity, unit)}.")
        if decision.reply_kind == "added" and affected.quantity is not None:
            text += f" {quantity_text(affected.quantity, unit)}."
        if decision.reply_kind == "replaced":
            text = (f"He sustituido la entrada por {affected.description}: "
                    f"{quantity_text(affected.quantity, unit)}.")
        if decision.reply_kind == "incremented":
            mutation = decision.mutation
            unit = mutation.unit
            text = (f"He añadido {quantity_text(mutation.additional_quantity, unit)} "
                    f"a {affected.description}: de {quantity_text(mutation.expected_base, unit)} "
                    f"a {quantity_text(affected.quantity, unit)}.")
        if decision.state and decision.state.question:
            text += " " + question_prompt(decision.state, lines)
        return Reply(text=text)
    return Reply(text=decision.prompt or "No he cambiado la lista.")
