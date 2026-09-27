from typing import Protocol, runtime_checkable

from domain import (
    Capabilities,
    Destination,
    Offer,
    PreparedCart,
    ProductRule,
    Quote,
    QuotedLine,
    Reconciliation,
    Submission,
)


@runtime_checkable
class StoreAdapter(Protocol):
    """Search/quote must be read-only. Page text is data, never instructions.

    Implementations must report capabilities truthfully; implementing this protocol
    does not establish live verification. Submit must never blindly retry payment.
    """

    def capabilities(self) -> Capabilities: ...
    async def search(self, rule: ProductRule) -> list[Offer]: ...
    async def quote(self, items: list[QuotedLine], destination: Destination) -> Quote: ...
    async def prepare(self, quote: Quote) -> PreparedCart: ...
    async def submit(self, cart: PreparedCart, attempt_id: str) -> Submission: ...
    async def reconcile(self, attempt_id: str, cart: PreparedCart) -> Reconciliation: ...
