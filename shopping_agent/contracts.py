"""Agent boundaries: model suggestions carry no identity or mutation authority."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, Field, field_validator, model_validator

from dialogue import (
    DIALOGUE_TTL,
    DialogueMutation,
    LineRef,
    PackageQuantity,
    Unit,
    canonical_name,
)
from domain import ListLine, Model, Positive, Reply, UtcTime


def nonblank(value: str) -> str:
    if not canonical_name(value):
        raise ValueError("text must not be blank")
    return value


Description = Annotated[str, Field(max_length=160), AfterValidator(nonblank)]
Condition = Annotated[str, Field(max_length=500), AfterValidator(nonblank)]
Position = Annotated[int, Field(ge=1, le=20)]
DuplicateDecision = Literal["separate", "set_total"]
Operation = Literal["add", "increment", "set_quantity", "replace"]


class ItemInput(Model):
    description: Description
    quantity: PackageQuantity | None = None
    # Missing units are unresolved data, never permission to use diaper units.
    unit: Unit | None = None


class ProposeAdds(Model):
    items: tuple[ItemInput, ...] = Field(min_length=1, max_length=20)
    condition: Condition | None = None


class ProposeChange(Model):
    kind: Literal["increment", "set_quantity", "replace"]
    query: Description
    quantity: PackageQuantity | None = None
    unit: Unit | None = None
    replacement: Description | None = None
    condition: Condition | None = None

    @model_validator(mode="after")
    def exclusive_replacement(self) -> Self:
        if (self.kind == "replace") != (self.replacement is not None):
            raise ValueError("replacement is required and exclusive to replace")
        return self


class ItemPatch(Model):
    position: Position
    quantity: PackageQuantity | None = None
    unit: Unit | None = None
    candidate_index: Positive | None = None
    duplicate_decision: DuplicateDecision | None = None


class CompleteProposal(Model):
    patches: tuple[ItemPatch, ...] = Field(max_length=20)
    remove_condition: bool = False

    @model_validator(mode="after")
    def unique_positions(self) -> Self:
        if len({patch.position for patch in self.patches}) != len(self.patches):
            raise ValueError("patch positions must be unique")
        return self


class ProposalItem(Model):
    """Application-owned resolution, separate from model-facing arguments."""

    position: Position
    kind: Operation
    description: Description
    quantity: PackageQuantity | None = None
    unit: Unit | None = None
    replacement: Description | None = None
    candidates: tuple[LineRef, ...] = ()
    target: LineRef | None = None
    base_quantity: PackageQuantity | None = None
    additional_quantity: PackageQuantity | None = None
    duplicate_decision: DuplicateDecision | None = None
    conflict_signatures: tuple[LineRef, ...] = ()
    # Positions of canonically conflicting outputs in this same batch.
    internal_conflicts: tuple[Position, ...] = ()

    @property
    def complete(self) -> bool:
        if self.quantity is None:
            return False
        if self.internal_conflicts and self.duplicate_decision is None:
            return False
        if self.kind == "add":
            if self.duplicate_decision == "set_total":
                return self.target is not None
            return not self.candidates or self.duplicate_decision is not None
        if self.target is None:
            return False
        if self.kind == "replace":
            # Selected origin candidates are not destination duplicates. Also
            # preserve the conservative gate for legacy destination-only tuples.
            has_conflicts = bool(self.conflict_signatures or (
                self.candidates and self.target not in self.candidates))
            return (self.replacement is not None
                    and (not has_conflicts or self.duplicate_decision is not None))
        if self.kind == "increment":
            return (self.base_quantity is not None and self.additional_quantity is not None
                    and self.quantity == self.base_quantity + self.additional_quantity)
        return True


class AgentProposal(Model):
    schema_version: Literal[1] = 1
    id: UUID
    revision: Positive
    user_id: int
    chat_id: int
    source_update_id: int
    original_text: str
    items: tuple[ProposalItem, ...] = Field(min_length=1, max_length=20)
    condition: Condition | None = None
    updated_at: UtcTime
    expires_at: UtcTime
    reviewed_revision: Positive | None = None
    reviewed_update_id: int | None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def strict_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @model_validator(mode="after")
    def valid_review(self) -> Self:
        if len({item.position for item in self.items}) != len(self.items):
            raise ValueError("item positions must be unique")
        if not self.updated_at < self.expires_at <= self.updated_at + DIALOGUE_TTL:
            raise ValueError("proposal lifetime must be positive and at most 15 minutes")
        if (self.reviewed_revision is None) != (self.reviewed_update_id is None):
            raise ValueError("review requires both revision and update id")
        if self.reviewed_revision is not None and (
            self.reviewed_revision != self.revision or self.condition is not None
            or not all(item.complete for item in self.items)
        ):
            raise ValueError("only a complete unconditional current revision can be reviewed")
        return self


class Reservation(Model):
    line_id: str
    order_id: str


class AgentSnapshot(Model):
    proposal: AgentProposal | None = None
    lines: tuple[ListLine, ...] = ()
    reservations: tuple[Reservation, ...] = ()
    user_id: int
    chat_id: int
    source_update_id: int
    original_text: str

    def model_context(self) -> dict:
        """JSON-safe context without inbox identity or authority fields."""
        return self.model_dump(mode="json", exclude={
            "user_id": True, "chat_id": True,
            "proposal": {"user_id", "chat_id"},
        })


DecisionReason = Literal[
    "pending", "reviewed", "confirmed", "cancelled", "rejected", "expired",
    "stale", "reserved", "quantity_range", "diaper_unit", "no_pending",
    "condition", "invalid",
]


class ProposalDecision(Model):
    proposal: AgentProposal | None = None
    reason: DecisionReason
    mutations: tuple[DialogueMutation, ...] = ()

    @model_validator(mode="after")
    def explicit_control_only(self) -> Self:
        if self.mutations and self.reason != "confirmed":
            raise ValueError("mutations require an explicit confirmation decision")
        return self


class ToolCall(Model):
    name: str
    arguments: dict


class ToolResult(Model):
    name: str
    data: dict
    reply: Reply
    terminal: bool


class AgentRunResult(Model):
    reply: Reply
    model_calls: Annotated[int, Field(ge=0)]
    tool_calls: Annotated[int, Field(ge=0)]
    reason: str
