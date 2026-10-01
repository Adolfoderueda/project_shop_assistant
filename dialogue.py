"""Bounded dialogue contracts and closed answers; no persistence or model calls."""

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Literal, Self

from pydantic import model_validator

from domain import Intent, Model, Positive, UtcTime, utc

DIALOGUE_TTL = timedelta(minutes=15)
Unit = Literal["envases", "paquetes", "botes", "sacos"]
Question = Literal[
    "add_or_replace", "duplicate_choice", "select_line", "quantity", "confirm_replace",
    "replace_quantity", "replace_duplicate", "remove_id",
]


class LineRef(Model):
    id: str
    revision: Positive


class ProductMention(Model):
    description: str
    source_update_id: int
    line: LineRef | None = None
    unit: Unit = "envases"


class DialogueState(Model):
    user_id: int
    chat_id: int
    focus: ProductMention | None
    target: LineRef | None = None
    candidates: tuple[LineRef, ...] = ()
    question: Question | None = None
    # Choice options are ordered action keys, not displayed Spanish labels.
    options: tuple[str, ...] = ()
    proposal_quantity: Positive | None = None
    replacement_confirmed: bool = False
    duplicate_confirmed: bool = False
    updated_at: UtcTime
    expires_at: UtcTime


class DialogueAnswer(Model):
    kind: Literal[
        "add", "replace", "change_quantity", "keep_quantity", "quantity", "confirm",
        "select", "remove_id", "cancel",
    ]
    quantity: Positive | None = None
    unit: Unit | None = None
    selection: Positive | None = None
    line_id: str | None = None


class DialogueMutation(Model):
    kind: Literal["add", "set_quantity", "replace"]
    description: str | None = None
    quantity: Positive | None = None
    target: LineRef | None = None
    unit: Unit = "envases"


class DialogueDecision(Model):
    mutation: DialogueMutation | None
    legacy_intent: Intent | None
    state: DialogueState | None
    prompt: str | None = None
    reply_kind: Literal[
        "clarify", "added", "updated", "replaced", "cancelled", "natural_list", "legacy",
    ]

    @model_validator(mode="after")
    def exclusive_action(self) -> Self:
        if self.mutation is not None and self.legacy_intent is not None:
            raise ValueError("mutation and legacy_intent are mutually exclusive")
        return self


def canonical_name(text: str) -> str:
    """Ignore accents, case and whitespace, never product qualifiers."""
    plain = "".join(
        char for char in unicodedata.normalize("NFD", text.casefold())
        if not unicodedata.combining(char)
    )
    return " ".join(plain.split())


def expired(state: DialogueState, now: datetime) -> bool:
    return utc(now) >= state.expires_at


def parse_answer(
    text: str, state: DialogueState | None, *, now: datetime,
) -> DialogueAnswer | None:
    """Parse only whole-message answers to a live, compatible question.

    References still require row/revision revalidation by the controller. Bare
    quantities carry no unit so the controller can preserve the question's label.
    """
    clean = canonical_name(text)
    if clean == "cancelar":
        return DialogueAnswer(kind="cancel")
    if state is None or expired(state, now):
        return None
    if clean == "no" and (state.question is not None or state.focus is not None):
        return DialogueAnswer(kind="cancel")
    question = state.question
    if question is None:
        return None
    if clean in {"si", "confirmo"} and question in {"confirm_replace", "replace_duplicate"}:
        return DialogueAnswer(kind="confirm")
    if question == "add_or_replace":
        if clean in {"anadelo", "anadelo a mi lista", "anade eso"} and "add" in state.options:
            return DialogueAnswer(kind="add")
        if clean == "sustituyelo" and "replace" in state.options:
            return DialogueAnswer(kind="replace")
    if question == "duplicate_choice":
        if clean == "anadir otra linea" and "add" in state.options:
            return DialogueAnswer(kind="add")
        if clean == "cambiar cantidad" and "change_quantity" in state.options:
            return DialogueAnswer(kind="change_quantity")
    if question == "replace_quantity" and clean == "conserva la cantidad":
        return DialogueAnswer(kind="keep_quantity")
    if question == "remove_id" and text.strip() in {line.id for line in state.candidates}:
        return DialogueAnswer(kind="remove_id", line_id=text.strip())
    if question in {"quantity", "replace_quantity"}:
        match = re.fullmatch(r"([1-9][0-9]*)(?: (envases|paquetes|botes|sacos))?", clean)
        if match:
            try:
                quantity = int(match[1])
            except ValueError:
                return None
            return DialogueAnswer(
                kind="quantity", quantity=quantity, unit=match[2],
            )
    if (
        question in {"select_line", "add_or_replace", "duplicate_choice"}
        and re.fullmatch(r"[1-9][0-9]*", clean)
    ):
        try:
            selection = int(clean)
        except ValueError:
            return None
        count = len(state.candidates) if question == "select_line" else len(state.options)
        if selection <= count:
            return DialogueAnswer(kind="select", selection=selection)
    return None
