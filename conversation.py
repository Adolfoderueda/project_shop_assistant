"""Conversation boundary. Registers orders, never executes or retries payment."""

import re

from domain import IncomingMessage, Intent, IntentLine, Reply
from interpreter import (
    Interpreter,
    clarify,
    diaper_reference,
    explicit_diaper_packs,
    normalized,
    parse_command,
    purchase_authorized,
    quantity,
)
from product_memory import identifiable_product_name
from storage import Repository


class Conversation:
    def __init__(self, repo: Repository, interpreter: Interpreter):
        self.repo = repo
        self.interpreter = interpreter

    async def handle(self, message: IncomingMessage, mode: str) -> Reply:
        # Consume only the durable inbox text, not a caller-supplied replacement.
        stored, reply = self.repo.message_result(message.update_id)
        if stored != message:
            raise ValueError("Message does not match durable inbox")
        if reply is not None:
            return reply
        lines = self.repo.list_lines()
        intent = parse_command(message.text, lines)
        pending = self.repo.pending_clarification(message.user_id)
        if (
            intent is None
            and pending
            and pending.action == "set_quantity"
            and quantity(message.text) is not None
        ):
            target = next((l for l in lines if l.id == pending.lines[0].line_id), None)
            if (
                target
                and diaper_reference(target.description)
                and not explicit_diaper_packs(message.text)
            ):
                intent = clarify(
                    "Indica paquetes de pañales explícitamente, no piezas ni unidades."
                )
            else:
                intent = Intent(
                    action="set_quantity",
                    lines=[
                        IntentLine(
                            line_id=pending.lines[0].line_id, quantity=quantity(message.text)
                        )
                    ],
                )
        if (
            intent is None
            and pending
            and pending.action == "remove"
            and message.text.strip() in {l.line_id for l in pending.lines}
        ):
            intent = Intent(action="remove", lines=[IntentLine(line_id=message.text.strip())])
        if intent is None:
            # Snapshot relevant observations only on the free-text route; do not
            # trust model-selected names as a database query without validation.
            requested = self._product_name(message.text)
            products = self.repo.find_products(requested) if requested is not None else []
            try:
                contextual = getattr(self.interpreter, "parse_with_context", None)
                if callable(contextual):
                    intent = await contextual(message.text, lines, products)
                else:
                    intent = await self.interpreter.parse(message.text, lines)
                intent = Intent.model_validate(intent.model_dump())
            except Exception:  # noqa: BLE001 -- untrusted interpreter boundary, fail closed
                intent = clarify()
            intent = self._validate_model(message.text, intent, lines)
        ids = {l.id for l in lines}
        if intent.action in ("remove", "set_quantity") and (
            not intent.lines or any(l.line_id not in ids for l in intent.lines)
        ):
            intent = clarify("Indica un ID existente de /lista.")
        if intent.action in ("status", "resume"):
            try:
                self.repo.get_order(intent.order_id)
            except (KeyError, TypeError):
                intent = clarify("Indica un ID de orden existente.")
        if intent.action == "buy" and not purchase_authorized(message.text):
            intent = clarify("No se ha autorizado ninguna compra. Usa /comprar para la lista.")
        return self.repo.apply_intent(message.update_id, intent, mode, conversation=True)

    @staticmethod
    def _product_name(text: str) -> str | None:
        clean = normalized(text).strip().removeprefix("¿").removesuffix("?").strip()
        match = re.fullmatch(
            r"(?:que sabes de (.+)|que (.+) vimos|tenemos ficha de (.+))", clean
        )
        if not match:
            return None
        name = next(group for group in match.groups() if group is not None).strip()
        if (
            not identifiable_product_name(name)
            or re.search(r'\b(?:no|nunca|si|o|u|y|cuando)\b|[?¿!¡.,;:"«»“”<>/\\]|https?\b|\n', name)
            or re.search(r"\b\d+\s+(?:paquetes?|botes?|sacos?|envases?|unidades?)\b", name)
        ):
            return None
        return name

    @staticmethod
    def _validate_model(text, intent, lines):
        if intent.action in ("buy", "resume", "remove", "set_quantity"):
            # Destructive actions require the deterministic route, not an LLM guess.
            return clarify("Usa /comprar, /continuar <id>, /quitar <id> o /cantidad <id> <n>.")
        if intent.action == "add":
            clean = normalized(text)
            match = re.fullmatch(r"(?:necesito|quiero|me hace falta|me hacen falta)\s+(.+)", clean)
            # Only a trailing closed courtesy phrase may be omitted from the
            # product. Validate the remaining request without relaxing its guards.
            requested = match[1].removesuffix(" por favor") if match else ""
            if not match or re.search(
                r'\b(no|nunca|si|o|u|y|cuando|gracias)\b|\b(?:en caso de|a menos que|por favor)\b|[?¿!¡.,;:"«»“”<>\\]|https?\b|\n',
                requested,
            ):
                return clarify()
            if len(intent.lines) != 1:
                return clarify()
            # Remove only a closed set of request prefixes, never product qualifiers.
            # Substring matching lets a model turn 'pienso de pollo' into the fish alias.
            for line in intent.lines:
                if not line.description or normalized(line.description) != requested:
                    return clarify(
                        "No puedo omitir características del producto. "
                        "Usa /anadir con la descripción completa."
                    )
                # A model cannot manufacture, omit or reinterpret explicit quantities.
                without_product_type = re.sub(r"\btipo\s+\d+\b", "", clean)
                if line.quantity is not None or re.search(r"\d", without_product_type):
                    return clarify(
                        "Indica producto y cantidad con /anadir <n> <envases> de <producto>."
                    )
                if line.url and line.url not in text:
                    return clarify()
        if intent.action == "product_query":
            requested = Conversation._product_name(text)
            if (
                requested is None
                or len(intent.lines) != 1
                or intent.order_id is not None
                or intent.question is not None
                or intent.lines[0].line_id is not None
                or intent.lines[0].quantity is not None
                or intent.lines[0].url is not None
                or not intent.lines[0].description
                or normalized(intent.lines[0].description).strip() != requested
            ):
                return clarify("Aclara el producto con una pregunta completa.")
        if intent.action == "clarify":
            # Only deterministic ambiguity resolution may persist candidate IDs.
            return clarify(intent.question or "Aclara el producto o usa un comando.")
        return intent
