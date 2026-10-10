"""Durable guided dialogue data; model candidates cannot confirm or save."""

import json
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, TypeAdapter, model_validator

from dialogue import DIALOGUE_TTL, DialogueMutation, Unit
from domain import Model, Positive, Reply, UtcTime
from shopping_agent.contracts import (
    AgentSnapshot,
    Condition,
    Description,
    GuidedProposal,
    ItemInput,
    ItemPatch,
    Positions,
    ProposeAdds,
    ProposeChange,
    ReviewWitness,
    SourceUpdateId,
)
from shopping_agent.contracts import (
    Contribution as Contribution,  # noqa: PLC0414 - public re-export
)
from shopping_agent.contracts import (
    StoredProposal as StoredProposal,  # noqa: PLC0414 - public re-export
)

QuestionKind = Literal[
    "scope", "quantity_shared", "quantity_single", "unit", "duplicate",
    "source_line", "condition", "topic", "review",
]
QuestionStatus = Literal["active", "consumed", "expired", "revoked"]
ChoiceKind = Literal[
    "one_each", "same_quantity", "different_quantities", "write_answer",
    "choose_scope", "choose_unit", "separate", "set_total", "choose_line",
    "remove_condition", "append_topic", "keep_topic", "confirm", "correct", "cancel",
]


class Choice(Model):
    kind: ChoiceKind
    label: Annotated[str, Field(min_length=1)]
    positions: Positions = ()
    candidate_index: Positive | None = None
    unit: Unit | None = None

    @model_validator(mode="after")
    def compatible_data(self) -> Self:
        if (self.kind == "choose_line") != (self.candidate_index is not None):
            raise ValueError("candidate index is required and exclusive to choose_line")
        if self.kind == "choose_line" and len(self.positions) != 1:
            raise ValueError("choose_line requires exactly one position")
        if (self.kind == "choose_unit") != (self.unit is not None):
            raise ValueError("unit is required and exclusive to choose_unit")
        if self.kind == "choose_scope" and not self.positions:
            raise ValueError("choose_scope requires positions")
        if self.positions and self.kind not in {
            "one_each", "same_quantity", "different_quantities", "choose_scope",
            "choose_unit", "separate", "set_total", "choose_line",
        }:
            raise ValueError("this choice does not carry positions")
        return self


class QuantityCandidate(Model):
    kind: Literal["quantity"] = "quantity"
    patches: tuple[ItemPatch, ...] = Field(min_length=1, max_length=20)
    source_update_id: SourceUpdateId

    @model_validator(mode="after")
    def unique_patches(self) -> Self:
        if len({patch.position for patch in self.patches}) != len(self.patches):
            raise ValueError("patch positions must be unique")
        return self


class ScopeCandidate(Model):
    kind: Literal["scope"] = "scope"
    positions: Annotated[Positions, Field(min_length=1)]
    source_update_id: SourceUpdateId


class TopicCandidate(Model):
    kind: Literal["topic"] = "topic"
    adds: ProposeAdds
    source_update_id: SourceUpdateId


class ChangeCandidate(Model):
    kind: Literal["change"] = "change"
    change: ProposeChange
    source_update_id: SourceUpdateId


class ReadCandidate(Model):
    kind: Literal["list", "fiche"]
    query: Description | None = None


class ControlCandidate(Model):
    kind: Literal["cancel", "clarify"]


GuidedAnswer = Annotated[
    QuantityCandidate | ScopeCandidate | TopicCandidate | ChangeCandidate | ReadCandidate | ControlCandidate,
    Field(discriminator="kind"),
]
_answer_adapter = TypeAdapter(GuidedAnswer)


def decode_guided_answer(payload: dict) -> GuidedAnswer:
    """Decode JSON-shaped application-stamped data, not native model authority."""
    return _answer_adapter.validate_json(json.dumps(payload))


class GuidedQuestion(Model):
    id: UUID
    version: Positive
    owner_id: int
    chat_id: int
    kind: QuestionKind
    proposal_id: UUID
    proposal_revision: Positive
    positions: Positions
    choices: tuple[Choice, ...] = Field(min_length=1)
    source_update_id: SourceUpdateId
    created_at: UtcTime
    expires_at: UtcTime
    status: QuestionStatus
    text: Annotated[str, Field(min_length=1)]
    candidate: QuantityCandidate | None = None

    @model_validator(mode="after")
    def valid_question(self) -> Self:
        if not self.created_at < self.expires_at <= self.created_at + DIALOGUE_TTL:
            raise ValueError("question lifetime must be positive and at most 15 minutes")
        offered = set(self.positions)
        if any(not set(choice.positions) <= offered for choice in self.choices):
            raise ValueError("choices must use offered positions")
        if self.candidate and any(patch.position not in offered for patch in self.candidate.patches):
            raise ValueError("candidate must use offered positions")
        return self


class PendingTopic(Model):
    id: UUID
    version: Positive
    source_update_id: SourceUpdateId
    original_text: str
    items: tuple[ItemInput, ...] = Field(min_length=1, max_length=20)
    condition: Condition | None = None
    proposal_id: UUID
    proposal_revision: Positive
    expires_at: UtcTime


class GuidedState(Model):
    snapshot: AgentSnapshot
    question: GuidedQuestion | None = None
    topic: PendingTopic | None = None
    review: ReviewWitness | None = None

    @model_validator(mode="after")
    def coherent_projection(self) -> Self:
        proposal = self.snapshot.proposal
        if proposal is not None and (
            proposal.user_id != self.snapshot.user_id or proposal.chat_id != self.snapshot.chat_id
        ):
            raise ValueError("proposal owner/chat must match the snapshot")
        expected_review = proposal.review if isinstance(proposal, GuidedProposal) else None
        if self.review != expected_review:
            raise ValueError("state review must project the proposal witness")
        for dependent in (self.question, self.topic):
            if dependent is None:
                continue
            if proposal is None or (
                dependent.proposal_id != proposal.id
                or dependent.proposal_revision != proposal.revision
                or dependent.expires_at > proposal.expires_at
            ):
                raise ValueError("question/topic must bind the current proposal and its lifetime")
        if self.question is not None and (
            self.question.owner_id != self.snapshot.user_id or self.question.chat_id != self.snapshot.chat_id
            or not set(self.question.positions) <= {item.position for item in proposal.items}
        ):
            raise ValueError("question owner/chat/positions must match the snapshot")
        if self.review is not None and self.question is not None and (
            self.question.kind != "review" or self.question.id != self.review.question_id
        ):
            raise ValueError("review witness must match the current review question")
        return self


class ResolvedChoice(Model):
    question_id: UUID
    question_version: Positive
    choice_index: Annotated[int, Field(ge=0)]
    source_update_id: SourceUpdateId


class GuidedDecision(Model):
    state: GuidedState
    reply: Reply
    mutations: tuple[DialogueMutation, ...] = ()
    reason: str

    @model_validator(mode="after")
    def explicit_delivered_review_only(self) -> Self:
        if self.mutations and (
            self.reason != "confirmed" or self.state.review is None
            or self.state.review.delivered_message_id is None
            or (self.state.question is not None and self.state.question.status in {"expired", "revoked"})
        ):
            raise ValueError("mutations require confirmation and a current delivered review witness")
        return self


class GuidedModelResult(Model):
    answer: GuidedAnswer | None
    reason: str
    model_calls: Annotated[int, Field(ge=0, le=4)]
    tool_calls: Annotated[int, Field(ge=0, le=8)]
