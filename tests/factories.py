from datetime import UTC, datetime

from domain import IncomingMessage, Intent, IntentLine, Offer


def message(update_id=1):
    return IncomingMessage(update_id=update_id, user_id=7, chat_id=7, text="petición")


def intent(action, **line):
    return Intent(action=action, lines=[IntentLine(**line)] if line else [])


def offer(**changes):
    values = {
        "store_id": "test",
        "product_id": "dog-food",
        "url": "https://example.com/item",
        "title": "Only Fish",
        "gtin": "8436586310295",
        "brand": "Alpha Spirit",
        "variant": "Only Fish",
        "grams": 12000,
        "units_per_pack": 1,
        "price_cents": 5000,
        "in_stock": True,
        "conditions": [],
        "observed_at": datetime.now(UTC),
    }
    return Offer(**(values | changes))
