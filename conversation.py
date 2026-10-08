"""Conversation boundary. Registers orders, never executes or retries payment."""

from collections.abc import Callable
from datetime import UTC, datetime

from dialogue import parse_answer
from dialogue_controller import closed_attempt, product_name, validate_model
from domain import IncomingMessage, Intent, Reply
from interpreter import Interpreter, clarify, parse_command, purchase_authorized
from presentation import PreparedPresentation, ReplyWriter
from presentation_validation import validate_draft, within_budget
from storage import Repository


class Conversation:
    def __init__(
        self, repo: Repository, interpreter: Interpreter,
        *, clock: Callable[[], datetime] | None = None,
        reply_writer: ReplyWriter | None = None,
    ):
        self.repo = repo
        self.interpreter = interpreter
        self.clock = clock or (lambda: datetime.now(UTC))
        self.reply_writer = reply_writer

    async def handle(self, message: IncomingMessage, mode: str) -> Reply:
        stored, reply = self.repo.message_result(message.update_id)
        if stored != message:
            raise ValueError("Message does not match durable inbox")
        if reply is not None:
            return reply
        # Recover the committed transition before reading current context or
        # interpreting anything, even if generation was disabled after restart.
        prepared = self.repo.prepared_presentation(message.update_id)
        if prepared is not None:
            return await self._present(prepared)
        lines = self.repo.list_lines()
        now = self.clock()
        state = self.repo.dialogue_state(message.user_id, message.chat_id, now=now)
        priority = message.text.strip().startswith("/") or purchase_authorized(message.text)
        if not priority and (
            parse_answer(message.text, state, now=now) is not None
            or closed_attempt(message.text)
        ):
            return await self._apply(message, None, mode, now=now, priority=False)
        intent = parse_command(message.text, lines)
        if intent is None:
            requested = product_name(message.text)
            products = self.repo.find_products(requested) if requested is not None else []
            try:
                dialogue = getattr(self.interpreter, "parse_with_dialogue", None)
                contextual = getattr(self.interpreter, "parse_with_context", None)
                if callable(dialogue):
                    intent = await dialogue(message.text, lines, products, state)
                elif callable(contextual):
                    intent = await contextual(message.text, lines, products)
                else:
                    intent = await self.interpreter.parse(message.text, lines)
                intent = Intent.model_validate_json(intent.model_dump_json())
            except Exception:  # noqa: BLE001 -- untrusted interpreter boundary, fail closed
                intent = clarify()
        # The repository reparses commands and validates proposals against durable
        # text/current rows in its transaction. No HTTP occurs in that transaction.
        return await self._apply(message, intent, mode, now=now, priority=priority)

    async def _apply(
        self, message: IncomingMessage, intent: Intent | None, mode: str,
        *, now: datetime, priority: bool,
    ) -> Reply:
        if self.reply_writer is None or priority:
            return self.repo.apply_dialogue(message.update_id, intent, mode, now=now)
        prepared = self.repo.prepare_dialogue(message.update_id, intent, mode, now=now)
        if isinstance(prepared, Reply):
            return prepared  # Operational replies remain deterministic.
        return await self._present(prepared)

    async def _present(self, prepared: PreparedPresentation) -> Reply:
        snapshot = prepared.snapshot
        reply = snapshot.fallback
        if self.reply_writer is not None and within_budget(snapshot):
            try:
                draft = await self.reply_writer.draft(snapshot)
                if draft is not None:
                    reply = validate_draft(snapshot, draft) or snapshot.fallback
            except Exception:  # noqa: BLE001 -- untrusted writer boundary, fail closed
                # CancelledError is a BaseException: leave the durable job pending.
                reply = snapshot.fallback
        # SQLite/provenance failures are not model failures and must propagate.
        return self.repo.finalize_presentation(prepared.update_id, reply)

    _product_name = staticmethod(product_name)
    _validate_model = staticmethod(validate_model)
