"""Conservative checkout orchestration; irreversible calls always have durable attempts."""

from domain import Destination, Quote, Submission
from offers import PurchaseRequest, cart_fingerprint, quote_is_complete, select_assignments
from restrictions import validate_product
from storage import Repository
from stores.base import StoreAdapter


class CheckoutService:
    def __init__(self, repo: Repository, stores: dict[str, StoreAdapter], destination: Destination):
        self.repo, self.stores, self.destination = repo, stores, destination

    def _requests(self, order):
        explicit = self.repo.purchase_requests(order.id)
        if explicit:
            if any(r.rule != self.repo.product_rule(r.rule.id) or not r.rule.verified for r in explicit):
                raise ValueError("Product verification changed")
            return explicit
        requests = []
        for line in order.lines:
            rule = self.repo.product_rule(line.product_id)
            if rule is None or not rule.verified or line.quantity is None or rule.id == "diapers":
                raise ValueError("Verify product and clarify quantity format")
            requests.append(PurchaseRequest(line_id=line.id, rule=rule, quantity=line.quantity))
        return requests

    def _valid_quote(self, quote, requests):
        rules = {r.line_id: r.rule for r in requests}
        return (quote_is_complete(quote) and bool(quote.delivery and quote.delivery.strip())
                and all(i.line_id in rules and not validate_product(rules[i.line_id], i.offer)
                        for i in quote.items))

    @staticmethod
    def _same_allocation(left, right):
        def identity(q):
            return sorted((i.line_id, i.packs, i.offer.model_dump_json(
                exclude={"price_cents", "observed_at", "title", "conditions", "in_stock"}))
                          for i in q.items)
        return left.store_id == right.store_id and identity(left) == identity(right)

    async def run(self, order_id: str) -> None:
        if not self.repo.claim_order(order_id):
            return
        try:
            if self.repo.order_status(order_id) not in ("pendiente", "preparado"):
                return
            order = self.repo.get_order(order_id)
            requests = self._requests(order)
            if self.destination.postcode != "28023" or not self.destination.address.strip():
                raise ValueError("Missing destination")
            subs = self.repo.suborders(order_id)
            if not subs:
                candidates = {r.line_id: [] for r in requests}
                stores = {}
                for sid, store in self.stores.items():
                    caps = store.capabilities()
                    if not caps.search or not caps.quote:
                        continue
                    if order.mode == "live" and not (caps.prepare and caps.submit and caps.reconcile
                                                     and caps.live_verified):
                        continue
                    stores[sid] = store
                    for req in requests:
                        try:
                            candidates[req.line_id].extend(o for o in await store.search(req.rule)
                                                           if o.store_id == sid)
                        except Exception:  # noqa: BLE001, S112 -- never log untrusted browser details
                            continue
                selection = await select_assignments(requests, candidates, stores, self.destination)
                if not selection.assignments:
                    raise ValueError("No exact verified basket")
                quotes = selection.assignments[0].quotes
                if not all(self._valid_quote(q, requests) for q in quotes):
                    raise ValueError("Delivery or identity missing")
                self.repo.save_assignment(order_id, quotes, simulated=order.mode == "dry_run")
                if order.mode == "dry_run":
                    return
                if not selection.coverage_complete:
                    self.repo.set_order_state(order_id, "preparado",
                                              "Comparación incompleta; no se afirma que sea la más barata.")
                subs = self.repo.suborders(order_id)
            for sub in subs:
                if sub["state"] != "preparado" or sub["result"] is not None:
                    continue
                store = self.stores[sub["store_id"]]
                caps = store.capabilities()
                if not all((caps.quote, caps.prepare, caps.submit, caps.reconcile, caps.live_verified)):
                    raise ValueError("Live checkout not verified")
                expected = Quote.model_validate_json(sub["quote_json"])
                fresh = await store.quote(expected.model_copy(deep=True).items, self.destination)
                if not self._valid_quote(fresh, requests) or not self._same_allocation(fresh, expected):
                    self.repo.set_order_state(order_id, "requiere_intervencion",
                                              "La cotización cambió; se necesita una nueva cotización verificada.")
                    return
                if cart_fingerprint(fresh) != cart_fingerprint(expected) or fresh.delivery != expected.delivery:
                    self.repo.refresh_quote(order_id, fresh)
                cart = await store.prepare(fresh.model_copy(deep=True))
                if (not self._valid_quote(cart.quote, requests) or cart.destination != self.destination
                        or cart.quote.delivery != fresh.delivery
                        or cart.fingerprint != cart_fingerprint(cart.quote)
                        or cart.fingerprint != cart_fingerprint(fresh)):
                    await store.quote(expected.model_copy(deep=True).items, self.destination)
                    self.repo.set_order_state(order_id, "requiere_intervencion",
                                              "El carrito o precio cambió; cotización solicitada de nuevo. Esta operación no se envió.")
                    return
                attempt = self.repo.save_attempt(order_id, sub["store_id"], cart)
                try:
                    result = await store.submit(cart.model_copy(deep=True), attempt)
                except Exception:  # noqa: BLE001 -- any submit error may follow an external purchase
                    result = Submission(status="uncertain", reason="submit response unavailable")
                self.repo.record_submission(attempt, result)
        except Exception:  # noqa: BLE001 -- preserve durable attempts; never expose browser secrets
            if any(self.repo.attempt_order(a) == order_id for a, _ in self.repo.uncertain_attempts()):
                self.repo.set_order_state(order_id, "resultado_incierto",
                                          "Resultado incierto; se reconciliará sin repetir la compra.")
            else:
                self.repo.set_order_state(order_id, "requiere_intervencion",
                                          "Operación bloqueada: faltan datos, referencia verificada o cotización válida. "
                                          "Consulta los resultados por tienda; no se repiten las compras confirmadas.")
        finally:
            self.repo.release_order(order_id)
