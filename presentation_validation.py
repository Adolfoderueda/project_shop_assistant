"""Fail-closed composition of application-owned facts, questions and options.

This initial frontier deliberately anchors all factual wording and the question.
The model chooses grouping/order and at most two approved introductory phrases;
it does not enjoy arbitrary prose freedom or an arbitrary-prose truth guarantee.
Expand this frontier only after user approval and new semantic tests.

Context budget counts compact snapshot JSON excluding fallback (never send that
private field to a model). Draft budget counts block text before substitution;
final budget includes newlines and application-inserted removal commands. Fallback
is never truncated or limited here. A rejected draft returns None for its caller
to select the complete fallback.
"""

import re
import unicodedata
from itertools import pairwise

from domain import Reply
from presentation import PresentationSnapshot, ReplyDraft

_TOKEN = re.compile(r"\{\{(f\d+|o\d+|q)\}\}")
_SEPARATORS = re.compile(r"(?:[\s.,:;•-]|\b(?:y|también|además)\b)*")
_LEADS = frozenset({
    "aqui tienes el detalle", "vamos por partes", "estas son las opciones",
    "te lo explico", "puedes elegir entre estas opciones",
})
_REMOVE_QUESTION = "Para quitar una entrada, envía su ID exacto o /quitar <id>."


def within_budget(snapshot: PresentationSnapshot) -> bool:
    """Check the complete public context, not the length of private fallback."""
    try:
        snapshot = PresentationSnapshot.model_validate_json(snapshot.model_dump_json())
    except (ValueError, TypeError):
        return False
    return (len(snapshot.facts) <= 20 and len(snapshot.options) <= 10
            and len(snapshot.model_dump_json(exclude={"fallback"})) <= 8000)


def _valid_lead(text: str) -> bool:
    if len(text) > 160:
        return False
    normalized = "".join(c for c in unicodedata.normalize("NFD", text.casefold())
                         if not unicodedata.combining(c))
    phrases = [p for p in re.split(r"[.\n]+", normalized) if p.strip()]
    return 1 <= len(phrases) <= 2 and all(
        " ".join(p.strip(" \t\r!¡?¿,;:").split()) in _LEADS for p in phrases)


def validate_draft(snapshot: PresentationSnapshot, draft: ReplyDraft) -> Reply | None:
    """Validate structure and full token coverage BEFORE literal substitution."""
    try:
        snapshot = PresentationSnapshot.model_validate_json(snapshot.model_dump_json())
        draft = ReplyDraft.model_validate_json(draft.model_dump_json())
    except (ValueError, TypeError):
        return None
    if not within_budget(snapshot) or sum(len(b.text) for b in draft.blocks) > 2000:
        return None
    # Contiguous local keys are part of the application snapshot contract.
    if ([f.key for f in snapshot.facts] != [f"f{i}" for i in range(len(snapshot.facts))]
            or [o.key for o in snapshot.options] != [f"o{i}" for i in range(len(snapshot.options))]):
        return None
    values = {f.key: f.text for f in snapshot.facts}
    values.update({o.key: o.text for o in snapshot.options})
    if snapshot.question is not None:
        values["q"] = snapshot.question
    seen: dict[str, list[str]] = {"fact": [], "question": [], "option": []}
    lead_count = 0
    for block in draft.blocks:
        if block.role == "lead":
            lead_count += 1
            if lead_count > 1 or not _valid_lead(block.text):
                return None
            continue
        matches = list(_TOKEN.finditer(block.text))
        if not matches or _SEPARATORS.fullmatch(_TOKEN.sub(" ", block.text)) is None:
            return None
        for previous, following in pairwise(matches):
            gap = block.text[previous.end():following.start()]
            if not gap or gap[0].isalpha() or gap[-1].isalpha():
                return None
        keys = [m.group(1) for m in matches]
        expected_prefix = {"fact": "f", "option": "o", "question": "q"}[block.role]
        if any(k not in values or not k.startswith(expected_prefix) for k in keys):
            return None
        seen[block.role].extend(keys)
    if (sorted(seen["fact"]) != sorted(f.key for f in snapshot.facts)
            or seen["option"] != [o.key for o in snapshot.options]
            or seen["question"] != (["q"] if snapshot.question is not None else [])
            or not values):
        return None
    # Single-pass replacement: inserted descriptions may themselves contain tokens.
    text = "\n".join(b.text if b.role == "lead" else
                     _TOKEN.sub(lambda m: values[m.group(1)], b.text) for b in draft.blocks)
    if snapshot.question == _REMOVE_QUESTION:
        # Task 1 keeps necessary row commands ONLY in the application fallback.
        # Recover its suffix by the exact typed public prefix, not by extracting
        # IDs from model output or interpreting descriptions as commands.
        public = "\n".join([*(f.text for f in snapshot.facts), snapshot.question,
                            *(o.text for o in snapshot.options)])
        if not snapshot.fallback.text.startswith(public + "\n"):
            return None
        text += snapshot.fallback.text[len(public):]
    if len(text) > 6000:
        return None
    return Reply(text=text, order_id=snapshot.fallback.order_id)
