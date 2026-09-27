"""Read-only basket comparison. No interpreter, credentials, or purchase actions."""

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from itertools import product
from typing import Literal

from pydantic import Field

from domain import Cents, Destination, Model, Offer, Positive, ProductRule, Quote, QuotedLine
from restrictions import validate_product
from stores.base import StoreAdapter


class PurchaseRequest(Model):
    """Explicit quantity semantics supplied by checkout after clarification.

    Diaper packs require confirmed pack_units; allocated pieces must sum exactly.
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
        and len({(i.line_id, i.offer.model_dump_json()) for i in quote.items}) == len(quote.items)
        and quote.shipping_cents is not None
        and quote.total_cents is not None
        and all(i.offer.store_id == quote.store_id and i.offer.in_stock
                and not i.offer.conditions for i in quote.items)
        and quote.total_cents == quote.shipping_cents + sum(
            i.packs * i.offer.price_cents for i in quote.items)
    )


def _contents(quote: Quote) -> tuple:
    contents = defaultdict(int)
    for i in quote.items:
        identity = (i.line_id, i.offer.product_id, i.offer.brand, i.offer.size,
                    i.offer.stage, i.offer.grams,
                    None if i.offer.product_id in ("diapers", "dog-food") else i.offer.variant,
                    None if i.offer.product_id == "diapers" else i.offer.gtin)
        contents[json.dumps(identity)] += i.packs * i.offer.units_per_pack
    return tuple(sorted(contents.items()))


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


def _allocation_units(request: PurchaseRequest, offer: Offer) -> int | None:
    """Amount of the requested quantity represented by one compatible pack."""
    if offer.product_id != request.rule.id or validate_product(request.rule, offer):
        return None
    if offer.conditions:
        return None
    if request.rule.id != "diapers" and request.rule.grams is None:
        return None
    if request.quantity_unit == "pieces":
        return offer.units_per_pack if request.rule.id == "diapers" else None
    units = request.pack_units
    if units is None:
        if request.rule.id == "diapers":
            return None
        units = 1
    return 1 if units == offer.units_per_pack else None


@dataclass
class _SearchBudget:
    remaining: int
    exceeded: bool = False

    def consume(self) -> bool:
        if not self.remaining:
            self.exceeded = True
            return False
        self.remaining -= 1
        return True


def _allocations(request: PurchaseRequest, offers: list[tuple[Offer, int]],
                 budget: _SearchBudget) -> list[list[QuotedLine]]:
    """Bounded iterative DFS over nonnegative pack counts, without rounding.

    Sibling counts are scheduled lazily: huge requested quantities do not build
    huge ranges/stacks. No recursion limit and no greedy price/shipping pruning.
    """
    if not offers:
        return []
    results = []
    stack = [(0, request.quantity, [], 0)]
    while stack:
        if not budget.consume():
            break
        index, remaining, chosen, count = stack.pop()
        offer, units = offers[index]
        if index == len(offers) - 1:
            if remaining % units == 0:
                count = remaining // units
                tail = [QuotedLine(line_id=request.line_id, offer=offer, packs=count)] if count else []
                results.append(chosen + tail)
            continue
        if (count + 1) * units <= remaining:
            stack.append((index, remaining, chosen, count + 1))
        tail = [QuotedLine(line_id=request.line_id, offer=offer, packs=count)] if count else []
        stack.append((index + 1, remaining - count * units, chosen + tail, 0))
    return results


async def select_assignments(
    requests: list[PurchaseRequest], candidates: Mapping[str, list[Offer]],
    stores: Mapping[str, StoreAdapter], destination: Destination,
    *, max_search_states: int = 10000,
) -> SelectionResult:
    """Enumerate exact pack allocations across compatible offers and stores.

    Coverage refers to supplied candidates, not the entire market. Allocation
    nodes and complete basket combinations share an explicit search budget.
    Hitting it reports incomplete coverage, never a globally cheapest claim.
    All returned baskets cover every requested line exactly, without mutation.
    """
    if not requests or len({r.line_id for r in requests}) != len(requests):
        raise ValueError("A nonempty request with unique line IDs is required")
    if type(max_search_states) is not int or max_search_states <= 0:
        raise ValueError("max_search_states must be a positive integer")
    budget = _SearchBudget(max_search_states)
    options, issues = [], []
    for req in requests:
        compatible, seen = [], set()
        for offer in candidates.get(req.line_id, []):
            units = _allocation_units(req, offer)
            identity = offer.model_dump_json()
            if units is not None and offer.store_id in stores and identity not in seen:
                compatible.append((offer, units))
                seen.add(identity)
        choices = _allocations(req, compatible, budget)
        options.append(choices)
        if not choices:
            issues.append(f"{req.line_id}: no compatible exact-quantity offer; clarify or verify")
    if budget.exceeded:
        issues.append("search limit reached; coverage incomplete; cheapest is not established")
    if any(not choices for choices in options):
        return SelectionResult(assignments=[], coverage_complete=False, issues=issues)
    assignments = []
    for combination in product(*options):
        if not budget.consume():
            issues.append("search limit reached; coverage incomplete; cheapest is not established")
            break
        grouped = defaultdict(list)
        for allocation in combination:
            for item in allocation:
                grouped[item.offer.store_id].append(item)
        quotes = []
        for store_id, items in grouped.items():
            try:
                # Frozen models contain mutable lists: isolate adapter input.
                quoted = await stores[store_id].quote(
                    [i.model_copy(deep=True) for i in items], destination)
                if (quoted.store_id != store_id or not quote_is_complete(quoted)
                        or sorted(i.model_dump_json() for i in quoted.items)
                        != sorted(i.model_dump_json() for i in items)):
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
