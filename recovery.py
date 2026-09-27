"""Reconcile durable attempts, including those interrupted before receiving a response."""

from domain import Submission
from storage import Repository
from stores.base import StoreAdapter


class Recovery:
    def __init__(self, repo: Repository, stores: dict[str, StoreAdapter]):
        self.repo, self.stores = repo, stores

    async def recover(self) -> None:
        self.repo.reclaim_abandoned_orders()
        orders = {self.repo.attempt_order(a) for a, _ in self.repo.uncertain_attempts()}
        orders.update(self.repo.resumable_orders())
        for oid in orders:
            if not self.repo.claim_order(oid):
                continue
            try:
                for attempt, cart in self.repo.uncertain_attempts():
                    if self.repo.attempt_order(attempt) != oid:
                        continue
                    store = self.stores.get(cart.quote.store_id)
                    try:
                        if store is None or not store.capabilities().reconcile:
                            continue
                        result = await store.reconcile(attempt, cart)
                        if result.status == "confirmed" and result.submission is not None:
                            self.repo.record_submission(attempt, result.submission)
                        elif result.status == "definitely_not_submitted":
                            self.repo.definitely_not_submitted(attempt)
                        else:
                            self.repo.record_submission(attempt, Submission(status="uncertain"))
                    except Exception:  # noqa: BLE001 -- no retry or raw adapter details on failure
                        self.repo.set_order_state(oid, "resultado_incierto",
                                                  "No se pudo reconciliar; no se repetirá la compra.")
                self.repo.finish_resume(oid)
            finally:
                self.repo.release_order(oid)
