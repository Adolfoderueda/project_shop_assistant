"""Durable presentation contracts, without action authority or I/O."""

import json
from typing import Literal, Protocol, Self

from pydantic import model_serializer, model_validator

from domain import Model, Reply

PresentationKind = Literal[
    "added", "updated", "replaced", "cancelled", "list", "product", "question", "clarify",
    "greeting", "pending_add", "incremented",
]
PresentationAct = Literal[
    "greeting", "pending_add", "select_entry", "increment_amount", "increment_confirm",
    "increment_missing", "increment_unknown", "result", "list", "cancel", "clarify",
]


class PresentationFact(Model):
    key: str
    text: str


class PresentationOption(Model):
    key: str
    text: str


class PresentationPhrase(Model):
    key: str
    role: Literal["fact", "question", "option"]
    variants: tuple[str, ...]


class PresentationSnapshot(Model):
    version: Literal[1, 2]
    kind: PresentationKind
    facts: tuple[PresentationFact, ...]
    options: tuple[PresentationOption, ...]
    question: str | None
    fallback: Reply
    act: PresentationAct | None = None
    phrases: tuple[PresentationPhrase, ...] = ()

    @model_serializer(mode="wrap")
    def compatible_serialization(self, handler):
        data = handler(self)
        if self.version == 1:
            if self.act is None:
                data.pop("act", None)
            if not self.phrases:
                data.pop("phrases", None)
        return data

    @model_validator(mode="after")
    def coherent_version(self) -> Self:
        if self.version == 1:
            if self.act is not None or self.phrases or self.kind in {
                "greeting", "pending_add", "incremented",
            }:
                raise ValueError("Version 1 cannot contain version 2 presentation contracts")
            return self
        from presentation_phrases import presentation_variants

        allowed = {
            "greeting": {"greeting"}, "pending_add": {"pending_add"},
            "select_entry": {"question"}, "increment_amount": {"question"},
            "increment_confirm": {"question"}, "increment_missing": {"question"},
            "increment_unknown": {"question"}, "result": {"added", "updated", "replaced", "incremented"},
            "list": {"list"}, "cancel": {"cancelled"}, "clarify": {"clarify", "question", "product"},
        }
        if self.act not in allowed or self.kind not in allowed[self.act]:
            raise ValueError("Presentation act must match its kind")
        if ([f.key for f in self.facts] != [f"f{i}" for i in range(len(self.facts))]
                or [o.key for o in self.options] != [f"o{i}" for i in range(len(self.options))]):
            raise ValueError("Presentation keys must be contiguous local references")
        if self.act == "greeting" and (
            len(self.facts) != 1 or self.facts[0].text != "¡Hola! ¿Qué necesitas para tu lista?"
            or self.options or self.question is not None
        ):
            raise ValueError("Greeting cannot carry product data or options")
        if self.act in {"pending_add", "select_entry", "increment_amount", "increment_confirm",
                        "increment_missing", "increment_unknown"} and self.question is None:
            raise ValueError("Pending acts require a question")
        if self.act in {"result", "list", "cancel"} and (self.question is not None or self.options):
            raise ValueError("Completed acts cannot carry pending questions")
        if not self.phrases or self.phrases != presentation_variants(self):
            raise ValueError("Presentation phrases must match the closed act grammar")
        return self


def public_presentation(snapshot: PresentationSnapshot) -> dict:
    """The single public contract used by both writer and context budget."""
    snapshot = PresentationSnapshot.model_validate_json(snapshot.model_dump_json())
    excluded = {"fallback"} | ({"act", "phrases"} if snapshot.version == 1 else set())
    return snapshot.model_dump(mode="json", exclude=excluded)


def public_presentation_json(snapshot: PresentationSnapshot) -> str:
    return json.dumps(public_presentation(snapshot), ensure_ascii=False, separators=(",", ":"))


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
