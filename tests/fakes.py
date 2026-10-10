import asyncio
from datetime import UTC, datetime
from functools import wraps
from types import SimpleNamespace

from telegram import Message, Update

from domain import Capabilities, PreparedCart, Quote, Reconciliation, Submission
from offers import cart_fingerprint


def async_test(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return run


class FakeStore:
    """Read-only quotes and an external purchase ledger that survives lost responses."""

    def __init__(self, store_id, offers):
        self.store_id, self.offers = store_id, offers
        self.prepare_calls = self.submit_calls = self.quote_calls = 0
        self.ledger = {}
        self.lose_response = False
        self.intervention = False
        self.change_cart = False
        self.before_submit = None
        self.after_commit = None
        self.destination = None

    def capabilities(self):
        return Capabilities(search=True, quote=True, prepare=True, submit=True,
                            reconcile=True, live_verified=True)

    async def search(self, rule):
        return [o for o in self.offers if o.product_id == rule.id]

    async def quote(self, items, destination):
        self.quote_calls += 1
        self.destination = destination
        return Quote(store_id=self.store_id, items=items, shipping_cents=0,
                     total_cents=sum(i.packs * i.offer.price_cents for i in items),
                     delivery="2 días", observed_at=datetime.now(UTC))

    async def prepare(self, quote):
        self.prepare_calls += 1
        if self.change_cart:
            quote = quote.model_copy(update={"shipping_cents": 100,
                                             "total_cents": quote.total_cents + 100})
        return PreparedCart(id="cart", quote=quote, fingerprint=cart_fingerprint(quote),
                            destination=self.destination)

    async def submit(self, cart, attempt_id):
        self.submit_calls += 1
        if self.before_submit:
            self.before_submit(attempt_id)
        if self.intervention:
            return Submission(status="requires_intervention", reason="bank verification")
        result = Submission(status="confirmed", external_id="external-" + attempt_id,
                            total_cents=cart.quote.total_cents, delivery=cart.quote.delivery)
        self.ledger[attempt_id] = result
        if self.after_commit:
            self.after_commit(attempt_id)
        if self.lose_response:
            raise TimeoutError("response lost after purchase")
        return result

    async def reconcile(self, attempt_id, cart):
        if attempt_id in self.ledger:
            return Reconciliation(status="confirmed", submission=self.ledger[attempt_id])
        return Reconciliation(status="unknown")


class FakeInterpreter:
    def __init__(self, result=None):
        self.result = result

    async def parse(self, text, lines):
        return self.result


class FakeBot:
    """In-memory Telegram boundary; real Update parsing and durable offset remain in use."""

    def __init__(self):
        self.updates = []
        self.sent = []

    def receive(self, number, text, user_id=7):
        self.updates.append(Update.de_json({
            "update_id": number,
            "message": {"message_id": number, "date": 1,
                        "chat": {"id": user_id, "type": "private"},
                        "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
                        "text": text},
        }, None))

    async def get_updates(self, *, offset, **kwargs):
        return [u for u in self.updates if u.update_id >= offset]

    async def send_message(self, *, chat_id, text, **kwargs):
        self.sent.append((chat_id, text))
        return Message.de_json({
            "message_id": len(self.sent), "date": 1,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": 99, "is_bot": True, "first_name": "Test bot"},
            "text": text,
        }, None)


class FakeOpenAI:
    def __init__(self, result=None, error=None):
        self.responses = self
        self.result = result
        self.error = error
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(output_parsed=self.result)
