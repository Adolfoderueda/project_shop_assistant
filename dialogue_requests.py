"""Whole-message source grammar and the untrusted proposal boundary."""

import re
from typing import Literal

from dialogue import canonical_name
from domain import Intent, ListLine, Model
from interpreter import clarify, normalized
from product_memory import identifiable_product_name


class SourceRequest(Model):
    action: Literal["greet", "add", "mention_product", "increment", "list", "product_query"]
    description: str | None = None


def product_name(text: str) -> str | None:
    """Legacy query guard, including its normalized return value."""
    clean = normalized(text).strip().removeprefix("¿").removesuffix("?").strip()
    match = re.fullmatch(r"(?:que sabes de (.+)|que (.+) vimos|tenemos ficha de (.+))", clean)
    if not match:
        return None
    name = next(group for group in match.groups() if group is not None).strip()
    if (not identifiable_product_name(name)
            or re.search(r'\b(?:no|nunca|si|o|u|y|cuando)\b|[?¿!¡.,;:"«»“”<>/\\]|https?\b|\n', name)
            or re.search(r"\b\d+\s+(?:paquetes?|botes?|sacos?|envases?|unidades?)\b", name)):
        return None
    return name


def classify_request(text: str) -> SourceRequest | None:
    raw = text.strip()
    clean = normalized(raw).strip("¿?¡!., ")
    if clean in {"hola", "hols", "buenas", "buenos dias", "hola que tal", "que tal"}:
        return SourceRequest(action="greet")
    social = re.match(r"hola(?:\s*,\s*|\s+)", raw, re.IGNORECASE)
    if social:
        raw = raw[social.end():]
        if raw.startswith("/"):
            return None
    clean = normalized(raw)
    if clean.strip("¿?¡!., ") in {
        "lista", "que hay en la lista", "que hay en mi lista", "muestra la lista",
        "muestra mi lista", "dame mi lista",
    }:
        return SourceRequest(action="list")
    if product_name(raw) is not None:
        original = raw.strip().removeprefix("¿").removesuffix("?").strip()
        if clean.lstrip("¿").startswith("que sabes de "):
            description = original.split(maxsplit=3)[-1]
        elif clean.lstrip("¿").startswith("que "):
            description = original.split(maxsplit=1)[-1].rsplit(maxsplit=1)[0]
        else:
            description = original.split(maxsplit=3)[-1]
        return SourceRequest(action="product_query", description=description)
    match = re.fullmatch(
        r"(quiero mas|anade mas|ahora|necesito|quiero|me hace falta|me hacen falta)\s+(.+)", clean,
    )
    if not match:
        return None
    prefix, requested = match.groups()
    requested = requested.removesuffix(" por favor")
    if re.search(
        r'\b(no|nunca|si|o|u|y|cuando|gracias)\b|\b(?:en caso de|a menos que|por favor)\b|[?¿!¡.,;:"«»“”<>\\]|https?\b|\n',
        requested,
    ):
        return None
    without_qualifiers = re.sub(r"\b(?:tipo|talla|etapa)\s+[1-9]\d*\b", "", requested)
    if re.search(r"\d", without_qualifiers):
        return None
    incremental = prefix in {"quiero mas", "anade mas"}
    if incremental and (not identifiable_product_name(requested)
                        or requested in {"eso", "esto", "mas", "lo mismo"}):
        return None
    if prefix == "quiero" and requested == "mas":
        return None
    original = raw.split(maxsplit=len(prefix.split()))[-1]
    if match[2].endswith(" por favor"):
        original = original.rsplit(" ", 2)[0]
    action = "increment" if incremental else "mention_product" if prefix == "ahora" else "add"
    return SourceRequest(action=action, description=original)


def literal_request(text: str) -> tuple[str, str] | None:
    request = classify_request(text)
    if request is not None and request.action in {"add", "mention_product"}:
        return request.action, request.description
    return None


def validate_request(text: str, proposal: Intent, lines: list[ListLine]) -> Intent:
    """Source evidence never grants model-selected quantities, identities or permissions."""
    if proposal.action in {"buy", "resume", "remove", "set_quantity", "status"}:
        return clarify("Usa un comando explícito para esa operación.")
    if proposal.action == "clarify":
        return clarify("Aclara el producto o la acción.")
    request = classify_request(text)
    if request is None or proposal.action != request.action:
        return clarify()
    if proposal.order_id is not None or proposal.question is not None:
        return clarify()
    if request.description is None:
        return proposal if not proposal.lines else clarify()
    if len(proposal.lines) != 1:
        return clarify()
    line = proposal.lines[0]
    if not line.description or canonical_name(line.description) != canonical_name(request.description):
        return clarify("No puedo omitir características del producto.")
    if line.line_id is not None or line.quantity is not None or line.url is not None:
        return clarify()
    return proposal
