"""Bounded dialogue contracts and closed answers; no persistence or model calls."""

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from domain import Intent, Model, Positive, UtcTime, utc

DIALOGUE_TTL = timedelta(minutes=15)
# Contextual quantities must fit SQLite's signed 64-bit INTEGER bindings.
MAX_QUANTITY = 2**63 - 1
PackageQuantity = Annotated[int, Field(gt=0, le=MAX_QUANTITY)]
Unit = Literal["envases", "paquetes", "botes", "sacos"]
Question = Literal[
    "add_or_replace", "duplicate_choice", "select_line", "quantity", "confirm_replace",
    "replace_quantity", "replace_duplicate", "remove_id",
    "add_quantity", "increment_quantity", "confirm_increment", "increment_missing", "increment_unknown",
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
    version: Literal[2] = 2
    pending_kind: Literal["add", "increment"] | None = None
    base_quantity: PackageQuantity | None = None
    additional_quantity: PackageQuantity | None = None
    increment_confirmed: bool = False
    user_id: int
    chat_id: int
    focus: ProductMention | None
    target: LineRef | None = None
    candidates: tuple[LineRef, ...] = ()
    question: Question | None = None
    # Choice options are ordered action keys, not displayed Spanish labels.
    options: tuple[str, ...] = ()
    proposal_quantity: PackageQuantity | None = None
    replacement_confirmed: bool = False
    duplicate_confirmed: bool = False
    updated_at: UtcTime
    expires_at: UtcTime

    @model_validator(mode="after")
    def valid_pending(self) -> Self:
        if self.pending_kind == "add":
            if (self.focus is None or self.focus.line is not None or self.target is not None
                    or self.base_quantity is not None or self.additional_quantity is not None
                    or self.increment_confirmed or self.replacement_confirmed):
                raise ValueError("Pending addition must not reference a saved line or increment")
            if self.question not in {None, "add_quantity", "duplicate_choice"}:
                raise ValueError("Pending addition requires an addition question")
            if self.duplicate_confirmed and not self.candidates:
                raise ValueError("Duplicate permission requires the offered saved references")
        if self.question == "add_quantity" and self.pending_kind != "add":
            raise ValueError("Addition quantity requires a pending addition")
        if self.question == "quantity" and self.pending_kind is not None:
            raise ValueError("Saved total quantity must not be a pending addition or increment")
        if self.question in {"increment_quantity", "confirm_increment", "increment_missing", "increment_unknown"} and self.pending_kind != "increment":
            raise ValueError("Increment question requires a pending increment")
        if self.pending_kind == "increment":
            if self.focus is None:
                raise ValueError("Pending increment requires a product focus")
            if self.question in {"increment_quantity", "increment_unknown"}:
                if self.target is None or self.focus.line != self.target:
                    raise ValueError("Increment quantity requires a selected saved reference")
                if (self.question == "increment_quantity") != (self.base_quantity is not None):
                    raise ValueError("Increment quantity question must match the known or unknown base")
        if self.pending_kind != "increment" and (self.base_quantity is not None
                or self.additional_quantity is not None or self.increment_confirmed):
            raise ValueError("Increment fields require a pending increment")
        if ((self.question == "confirm_increment" or self.increment_confirmed)
                and (self.target is None or self.focus is None or self.focus.line != self.target
                     or self.base_quantity is None or self.additional_quantity is None
                     or self.proposal_quantity != self.base_quantity + self.additional_quantity)):
            raise ValueError("Increment requires a coherent origin, base, delta and total")
        return self


class DialogueAnswer(Model):
    kind: Literal[
        "add", "replace", "change_quantity", "keep_quantity", "quantity", "confirm",
        "select", "remove_id", "cancel", "reject",
    ]
    quantity: PackageQuantity | None = None
    unit: Unit | None = None
    selection: Positive | None = None
    line_id: str | None = None


class DialogueMutation(Model):
    kind: Literal["add", "set_quantity", "replace", "increment"]
    expected_base: PackageQuantity | None = None
    additional_quantity: PackageQuantity | None = None
    description: str | None = None
    quantity: PackageQuantity | None = None
    target: LineRef | None = None
    unit: Unit = "envases"

    @model_validator(mode="after")
    def valid_increment(self) -> Self:
        if self.kind == "increment":
            if (self.target is None or self.description is None or self.expected_base is None
                    or self.additional_quantity is None
                    or self.quantity != self.expected_base + self.additional_quantity):
                raise ValueError("Increment requires identity and coherent arithmetic")
        elif self.expected_base is not None or self.additional_quantity is not None:
            raise ValueError("Increment operands are exclusive to increment mutations")
        return self


class DialogueDecision(Model):
    mutation: DialogueMutation | None
    legacy_intent: Intent | None
    state: DialogueState | None
    prompt: str | None = None
    presentation_reason: Literal[
        "generic", "expired", "stale", "reserved", "quantity_range", "diaper_unit",
        "no_pending", "cancelled_pending",
    ] = "generic"
    reply_kind: Literal[
        "clarify", "added", "updated", "replaced", "cancelled", "natural_list", "legacy",
        "pending_add", "greeting", "incremented",
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
    if clean == "no" and state.question == "confirm_increment":
        return DialogueAnswer(kind="reject")
    if clean == "no" and (state.question is not None or state.focus is not None):
        return DialogueAnswer(kind="cancel")
    question = state.question
    if question is None:
        return None
    if clean in {"si", "confirmo"} and question in {"confirm_replace", "replace_duplicate", "confirm_increment"}:
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
    if question in {"increment_missing", "increment_unknown"}:
        if clean in {"anadelo", "anadir otra linea"} and "add" in state.options:
            return DialogueAnswer(kind="add")
        if clean == "cambiar cantidad" and "change_quantity" in state.options:
            return DialogueAnswer(kind="change_quantity")
    if question == "replace_quantity" and clean == "conserva la cantidad":
        return DialogueAnswer(kind="keep_quantity")
    if question == "remove_id" and text.strip() in {line.id for line in state.candidates}:
        return DialogueAnswer(kind="remove_id", line_id=text.strip())
    if question in {"quantity", "replace_quantity", "add_quantity", "increment_quantity"}:
        match = re.fullmatch(r"([1-9][0-9]*)(?: (envases|paquetes|botes|sacos))?", clean)
        if match:
            try:
                quantity = int(match[1])
            except ValueError:
                return None
            if quantity > MAX_QUANTITY:
                return None
            return DialogueAnswer(
                kind="quantity", quantity=quantity, unit=match[2],
            )
    if (
        question in {"select_line", "add_or_replace", "duplicate_choice", "increment_missing", "increment_unknown"}
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
