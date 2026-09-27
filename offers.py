"""Read-only basket comparison. No interpreter, credentials, or purchase actions."""

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from decimal import Decimal
from itertools import product
from typing import Literal

from pydantic import Field

from domain import Cents, Destination, Model, Offer, Positive, ProductRule, Quote, QuotedLine
from restrictions import validate_product
from stores.base import StoreAdapter


class PurchaseRequest(Model):
    """Explicit quantity semantics supplied by checkout after clarification.

    Diaper packs require confirmed pack_units; pieces must divide exactly.
    Formula/food packs refer to the rule's confirmed gram format (one container
    per pack unless pack_units was explicitly confirmed).
    """

    line_id: str
    rule: ProductRule
    quantity: Positive
    quantity_unit: Literal["packs", "pieces"] = "packs"
    pack_units: Positive | None = None


class Assignment(Model):
    quotes: list[Quote]
    total_cents: Cents


class SelectionResult(Model):
    assignments: list[Assignment]
    coverage_complete: bool
    issues: list[str] = Field(default_factory=list)


def unit_price(offer: Offer) -> Decimal:
    """Informational cents per piece, never a ranking criterion."""
    return Decimal(offer.price_cents) / offer.units_per_pack


def quote_is_complete(quote: Quote) -> bool:
    """Conservative: conditional prices are not proven universal discounts.

    An adapter may emit an unconditional price only after verifying eligibility
    for this concrete basket/account without changing quantities/subscriptions.
    Unmodelled discounts/fees must remain unresolved, not silently guessed.
    """
    return bool(
        quote.items
        and len({i.line_id for i in quote.items}) == len(quote.items)
        and quote.shipping_cents is not None
        and quote.total_cents is not None
        and all(i.offer.store_id == quote.store_id and i.offer.in_stock
                and not i.offer.conditions for i in quote.items)
        and quote.total_cents == quote.shipping_cents + sum(
            i.packs * i.offer.price_cents for i in quote.items)
    )


def _contents(quote: Quote) -> tuple:
    return tuple(sorted((i.line_id, i.offer.product_id, i.offer.brand,
                         i.offer.size, i.offer.stage, i.offer.grams,
                         None if i.offer.product_id in ("diapers", "dog-food")
                         else i.offer.variant,
                         # Diaper range/GTIN can vary when pieces and size match.
                         None if i.offer.product_id == "diapers" else i.offer.gtin,
                         i.packs * i.offer.units_per_pack) for i in quote.items))


def rank_quotes(quotes: list[Quote]) -> list[Quote]:
    complete = [q for q in quotes if quote_is_complete(q)]
    if complete and any(_contents(q) != _contents(complete[0]) for q in complete[1:]):
        raise ValueError("Quotes must have comparable contents")
    return sorted(complete, key=lambda q: (q.total_cents, q.store_id))


def cart_fingerprint(quote: Quote) -> str:
    """Stable identity/quantity/price digest for prepare and pre-submit checks.

    Not an authorization token. Checkout must separately revalidate freshness,
    restrictions, conditions, and complete totals before any submission.
    """
    items = sorted((i.line_id, i.offer.product_id, i.offer.url, i.offer.gtin,
                    i.offer.brand, i.offer.variant, i.offer.stage, i.offer.size,
                    i.offer.grams, i.offer.units_per_pack, i.packs, i.offer.price_cents)
                   for i in quote.items)
    payload = [quote.store_id, quote.currency, items, quote.shipping_cents, quote.total_cents]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True).encode()).hexdigest()


def _packs(request: PurchaseRequest, offer: Offer) -> int | None:
    if offer.product_id != request.rule.id or validate_product(request.rule, offer):
        return None
    if offer.conditions:
        return None
    if request.rule.id != "diapers" and request.rule.grams is None:
        return None
    if request.quantity_unit == "pieces":
        if request.rule.id != "diapers" or request.quantity % offer.units_per_pack:
            return None
        return request.quantity // offer.units_per_pack
    units = request.pack_units
    if units is None:
        if request.rule.id == "diapers":
            return None
        units = 1
    return request.quantity if units == offer.units_per_pack else None


async def select_assignments(
    requests: list[PurchaseRequest], candidates: Mapping[str, list[Offer]],
    stores: Mapping[str, StoreAdapter], destination: Destination,
) -> SelectionResult:
    """Enumerate every whole-line offer/store assignment; quote grouped baskets.

    Coverage refers to supplied candidates, not the entire market. No mutation,
    implicit pack rounding, or hidden cap on the search space. Callers must keep
    candidate sets small. All requested lines must be covered in every result.
    """
    if not requests or len({r.line_id for r in requests}) != len(requests):
        raise ValueError("A nonempty request with unique line IDs is required")
    options, issues = [], []
    for req in requests:
        choices = []
        for offer in candidates.get(req.line_id, []):
            packs = _packs(req, offer)
            if packs is not None and offer.store_id in stores:
                choices.append(QuotedLine(line_id=req.line_id, offer=offer, packs=packs))
        options.append(choices)
        if not choices:
            issues.append(f"{req.line_id}: no compatible exact-quantity offer; clarify or verify")
    if issues:
        return SelectionResult(assignments=[], coverage_complete=False, issues=issues)
    assignments = []
    for combination in product(*options):
        grouped = defaultdict(list)
        for item in combination:
            grouped[item.offer.store_id].append(item)
        quotes = []
        for store_id, items in grouped.items():
            try:
                # Frozen models contain mutable lists: isolate adapter input.
                quoted = await stores[store_id].quote(
                    [i.model_copy(deep=True) for i in items], destination)
                if (quoted.store_id != store_id or not quote_is_complete(quoted)
                        or sorted(quoted.items, key=lambda i: i.line_id)
                        != sorted(items, key=lambda i: i.line_id)):
                    raise ValueError("Unverifiable quote")
            except Exception:  # noqa: BLE001 -- adapter failure excludes only this combination
                # No raw browser exception: it may contain credentials/address.
                issues.append(f"{store_id}: combination has no verifiable quote")
                break
            quotes.append(quoted)
        else:
            assignments.append(Assignment(quotes=quotes,
                                          total_cents=sum(q.total_cents for q in quotes)))
    assignments.sort(key=lambda a: a.total_cents)
    return SelectionResult(assignments=assignments, coverage_complete=not issues,
                           issues=list(dict.fromkeys(issues)))
