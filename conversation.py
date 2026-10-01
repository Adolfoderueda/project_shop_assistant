"""Conversation boundary. Registers orders, never executes or retries payment."""

from collections.abc import Callable
from datetime import UTC, datetime

from dialogue import parse_answer
from dialogue_controller import closed_attempt, product_name, validate_model
from domain import IncomingMessage, Intent, Reply
from interpreter import Interpreter, clarify, parse_command, purchase_authorized
from storage import Repository


class Conversation:
    def __init__(
        self, repo: Repository, interpreter: Interpreter,
        *, clock: Callable[[], datetime] | None = None,
    ):
        self.repo = repo
        self.interpreter = interpreter
        self.clock = clock or (lambda: datetime.now(UTC))

    async def handle(self, message: IncomingMessage, mode: str) -> Reply:
        stored, reply = self.repo.message_result(message.update_id)
        if stored != message:
            raise ValueError("Message does not match durable inbox")
        if reply is not None:
            return reply
        lines = self.repo.list_lines()
        now = self.clock()
        state = self.repo.dialogue_state(message.user_id, message.chat_id, now=now)
        priority = message.text.strip().startswith("/") or purchase_authorized(message.text)
        if not priority and (
            parse_answer(message.text, state, now=now) is not None
            or closed_attempt(message.text)
        ):
            return self.repo.apply_dialogue(message.update_id, None, mode, now=now)
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
        return self.repo.apply_dialogue(message.update_id, intent, mode, now=now)

    _product_name = staticmethod(product_name)
    _validate_model = staticmethod(validate_model)
