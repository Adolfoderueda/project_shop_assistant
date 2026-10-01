"""Replies built from rows actually saved, not model-generated prose."""

from dialogue import DialogueDecision
from dialogue_controller import question_prompt
from domain import ListLine, Reply


def render_dialogue_result(
    decision: DialogueDecision, affected: ListLine | None, lines: list[ListLine],
    legacy_reply: Reply | None = None,
) -> Reply:
    if decision.reply_kind == "legacy":
        return legacy_reply or Reply(text="No he cambiado la lista.")
    if decision.reply_kind == "natural_list":
        return Reply(text="\n".join(f"{l.description}: {l.quantity or '?'} envases" for l in lines)
                     or "La lista está vacía.")
    if affected and decision.reply_kind in {"added", "updated"}:
        unit = decision.state.focus.unit if decision.state and decision.state.focus else "envases"
        text = (f"He añadido {affected.description}." if decision.reply_kind == "added"
                else f"{affected.description}: {affected.quantity} {unit}.")
        if decision.reply_kind == "added" and affected.quantity is not None:
            text += f" {affected.quantity} {unit}."
        if decision.state and decision.state.question:
            text += " " + question_prompt(decision.state, lines)
        return Reply(text=text)
    return Reply(text=decision.prompt or "No he cambiado la lista.")
