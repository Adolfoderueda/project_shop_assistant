"""Shared strict contracts. Money is integer EUR cents; timestamps are UTC."""

from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_serializer

Positive = Annotated[int, Field(gt=0)]
Cents = Annotated[int, Field(ge=0)]


def utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    return value


UtcTime = Annotated[datetime, AfterValidator(utc)]
Mode = Literal["dry_run", "live"]
SuborderState = Literal[
    "pendiente_datos",
    "buscando",
    "preparado",
    "enviando",
    "confirmado",
    "requiere_intervencion",
    "resultado_incierto",
    "fallido",
    "cancelado",
]
SuborderResult = Literal["simulado", "confirmado"]


class Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class IncomingMessage(Model):
    update_id: int
    user_id: int
    chat_id: int
    text: str


CallbackToken = Annotated[str, Field(pattern=r"^q:[A-Za-z0-9_-]{22}$", min_length=24, max_length=24)]


class IncomingCallback(Model):
    kind: Literal["callback"] = "callback"
    update_id: int
    user_id: int
    chat_id: int
    callback_query_id: Annotated[str, Field(min_length=1)]
    message_id: Positive
    bot_id: Positive
    data: CallbackToken


IncomingEvent = IncomingMessage | IncomingCallback


def decode_event(payload: dict) -> IncomingEvent:
    """Dispatch only on an explicit transport kind, never on message text."""
    if "kind" not in payload:
        return IncomingMessage.model_validate(payload)
    return IncomingCallback.model_validate(payload)


class InlineButton(Model):
    label: Annotated[str, Field(min_length=1)]
    token: CallbackToken


class InlineKeyboard(Model):
    rows: tuple[tuple[InlineButton, ...], ...]


class ProductRule(Model):
    id: str
    brand: str
    variant: str | None = None
    stage: Positive | None = None
    size: Positive | None = None
    grams: Positive | None = None
    gtin: str | None = None
    verified: bool


class ListLine(Model):
    id: str
    product_id: str | None = None
    description: str
    quantity: Positive | None = None
    revision: Positive


class IntentLine(Model):
    line_id: str | None = None
    description: str | None = None
    quantity: Positive | None = None
    url: str | None = None


class Intent(Model):
    action: Literal[
        "add", "remove", "set_quantity", "list", "product_query", "mention_product", "buy",
        "status", "resume", "clarify", "greet", "increment",
    ]
    lines: list[IntentLine] = Field(default_factory=list)
    order_id: str | None = None
    question: str | None = None


class Reply(Model):
    text: str
    order_id: str | None = None
    keyboard: InlineKeyboard | None = None

    @model_serializer(mode="wrap")
    def compatible_serialization(self, handler):
        data = handler(self)
        if self.keyboard is None:
            data.pop("keyboard", None)
        return data


class Order(Model):
    id: str
    lines: list[ListLine]
    mode: Mode


class Offer(Model):
    store_id: str
    product_id: str
    url: str
    title: str
    gtin: str | None = None
    brand: str
    variant: str | None = None
    stage: Positive | None = None
    size: Positive | None = None
    grams: Positive | None = None
    units_per_pack: Positive
    price_cents: Cents
    in_stock: bool
    conditions: list[str]
    observed_at: UtcTime


class Destination(Model):
    postcode: str
    address: str = Field(repr=False)


class QuotedLine(Model):
    line_id: str
    offer: Offer
    packs: Positive


class Quote(Model):
    store_id: str
    items: list[QuotedLine]
    shipping_cents: Cents | None = None
    total_cents: Cents | None = None
    currency: Literal["EUR"] = "EUR"
    delivery: str | None = None
    observed_at: UtcTime


class Capabilities(Model):
    search: bool
    quote: bool
    prepare: bool
    submit: bool
    reconcile: bool
    live_verified: bool


class PreparedCart(Model):
    id: str
    quote: Quote
    fingerprint: str
    # Extracted checkout destination, not merely the requested address.
    destination: Destination | None = Field(default=None, repr=False)


class Submission(Model):
    status: Literal["confirmed", "requires_intervention", "uncertain", "failed"]
    external_id: str | None = None
    total_cents: Cents | None = None
    delivery: str | None = None
    reason: str | None = None


class Reconciliation(Model):
    status: Literal["confirmed", "definitely_not_submitted", "unknown"]
    submission: Submission | None = None
