"""Durable presentation contracts, without action authority or I/O."""

from typing import Literal, Protocol

from domain import Model, Reply

PresentationKind = Literal[
    "added", "updated", "replaced", "cancelled", "list", "product", "question", "clarify",
]


class PresentationFact(Model):
    key: str
    text: str


class PresentationOption(Model):
    key: str
    text: str


class PresentationSnapshot(Model):
    version: Literal[1]
    kind: PresentationKind
    facts: tuple[PresentationFact, ...]
    options: tuple[PresentationOption, ...]
    question: str | None
    fallback: Reply


class PreparedPresentation(Model):
    update_id: int
    user_id: int
    chat_id: int
    snapshot: PresentationSnapshot


class DraftBlock(Model):
    role: Literal["lead", "fact", "question", "option"]
    text: str


class ReplyDraft(Model):
    blocks: tuple[DraftBlock, ...]


class ReplyWriter(Protocol):
    async def draft(self, snapshot: PresentationSnapshot) -> ReplyDraft | None: ...
