"""Checkout persistence mixed into Repository; transactions never perform I/O to stores.

The runtime must hold its process lock. The local claim set distinguishes abandoned
durable claims from active coroutines when recovery runs in the same process.
"""

import json
from threading import RLock
from uuid import uuid4

from domain import PreparedCart, ProductRule, Quote, Reply, Submission
from offers import PurchaseRequest, cart_fingerprint

_active = set()
_lock = RLock()


class CheckoutRepository:
    def _require_purchase_execution(self):
        if not getattr(self, "purchases_enabled", True):
            raise PermissionError("Purchases disabled in experimental deployment")

    @staticmethod
    def _owns_reservations(db, order_id):
        execution = db.execute("SELECT legacy_quarantined FROM execution WHERE order_id=?",
                               (order_id,)).fetchone()
        if execution is None or execution[0]:
            return False
        subs = db.execute("SELECT state,quote_json FROM suborders WHERE order_id=?", (order_id,)).fetchall()
        for snapshot in db.execute("SELECT line_json FROM order_lines WHERE order_id=?", (order_id,)):
            line = json.loads(snapshot[0])
            # A local conflict resolution must not reassign a previously fulfilled
            # snapshot, even if its old reservation has already been released.
            fulfilled_elsewhere = db.execute(
                "SELECT 1 FROM order_lines l JOIN suborders s ON s.order_id=l.order_id "
                "JOIN json_each(s.quote_json,'$.items') i "
                "WHERE s.order_id!=? AND s.state='confirmado' "
                "AND json_extract(l.line_json,'$.id')=? AND json_extract(l.line_json,'$.revision')=? "
                "AND json_extract(i.value,'$.line_id')=? LIMIT 1",
                (order_id, line["id"], line["revision"], line["id"])).fetchone()
            if fulfilled_elsewhere:
                return False
            allocations = [s for s in subs if s["quote_json"] and any(
                i.line_id == line["id"] for i in Quote.model_validate_json(s["quote_json"]).items)]
            if allocations and all(s["state"] == "confirmado" for s in allocations):
                continue
            owner = db.execute("SELECT order_id FROM reservations WHERE line_id=?", (line["id"],)).fetchone()
            if owner is None or owner[0] != order_id:
                return False
        return True

    def require_checkout_reservations(self, order_id):
        with self._connection() as db:
            if not self._owns_reservations(db, order_id):
                raise ValueError("Snapshot quarantined, fulfilled elsewhere or not reserved by this order")

    def product_rule(self, product_id):
        with self._connection() as db:
            row = db.execute("SELECT rule_json FROM products WHERE id=?", (product_id,)).fetchone()
            return ProductRule.model_validate_json(row[0]) if row else None

    def pending_orders(self) -> list[str]:
        with self._connection() as db:
            candidates = [r[0] for r in db.execute(
                "SELECT order_id FROM execution WHERE state IN ('pendiente','preparado') "
                "AND claimed=0 AND legacy_quarantined=0 AND NOT EXISTS "
                "(SELECT 1 FROM suborders s WHERE s.order_id=execution.order_id AND s.awaiting_resume=1) "
                "ORDER BY rowid")]
            return [oid for oid in candidates if self._owns_reservations(db, oid)]

    def resumable_orders(self) -> list[str]:
        with self._connection() as db:
            return [r[0] for r in db.execute(
                "SELECT order_id FROM execution WHERE resume_requested=1 AND claimed=0 AND legacy_quarantined=0")]

    def order_status(self, order_id: str) -> str:
        with self._connection() as db:
            row = db.execute("SELECT state FROM execution WHERE order_id=?", (order_id,)).fetchone()
            if row is None:
                raise KeyError(order_id)
            return row[0]

    def claim_order(self, order_id: str) -> bool:
        self._require_purchase_execution()
        with _lock, self._connection(write=True) as db:
            changed = db.execute("UPDATE execution SET claimed=1 WHERE order_id=? AND claimed=0",
                                 (order_id,)).rowcount
            if changed:
                _active.add((str(self.path.resolve()), order_id))
            return bool(changed)

    def release_order(self, order_id: str) -> None:
        self._require_purchase_execution()
        with _lock, self._connection(write=True) as db:
            db.execute("UPDATE execution SET claimed=0 WHERE order_id=?", (order_id,))
            _active.discard((str(self.path.resolve()), order_id))

    def reclaim_abandoned_orders(self) -> None:
        """Only safe under the runtime's exclusive OS process lock."""
        self._require_purchase_execution()
        with _lock, self._connection(write=True) as db:
            for row in db.execute("SELECT order_id FROM execution WHERE claimed=1").fetchall():
                if (str(self.path.resolve()), row[0]) not in _active:
                    db.execute("UPDATE execution SET claimed=0 WHERE order_id=?", (row[0],))

    @staticmethod
    def _notice(db, order_id, text):
        chat = db.execute("SELECT i.chat_id FROM orders o JOIN inbox i "
                          "ON i.update_id=o.source_update_id WHERE o.id=?", (order_id,)).fetchone()[0]
        db.execute("INSERT INTO outbox(id,chat_id,reply_json) VALUES (?,?,?)",
                   (str(uuid4()), chat, Reply(text=text, order_id=order_id).model_dump_json()))

    def set_order_state(self, order_id, state, text):
        self._require_purchase_execution()
        with self._connection(write=True) as db:
            db.execute("UPDATE execution SET state=? WHERE order_id=?", (state, order_id))
            self._notice(db, order_id, text)

    def set_purchase_requests(self, order_id, requests: list[PurchaseRequest]):
        """Persist explicitly clarified quantity semantics before execution, never infer pieces."""
        self._require_purchase_execution()
        order = self.get_order(order_id)
        if ({r.line_id: r.quantity for r in requests}
                != {l.id: l.quantity for l in order.lines} or len(requests) != len(order.lines)):
            raise ValueError("Requests must match the authorized snapshot")
        for line, req in ((l, next(r for r in requests if r.line_id == l.id)) for l in order.lines):
            if req.rule != self.product_rule(line.product_id):
                raise ValueError("Rule must match the local catalog")
        with self._connection(write=True) as db:
            if not self._owns_reservations(db, order_id):
                raise ValueError("Snapshot is not executable")
            row = db.execute("SELECT state,claimed FROM execution WHERE order_id=?", (order_id,)).fetchone()
            if row[1] or db.execute("SELECT 1 FROM suborders WHERE order_id=?", (order_id,)).fetchone():
                raise ValueError("Checkout already started")
            db.execute("UPDATE execution SET requests_json=?,state='pendiente' WHERE order_id=?",
                       (json.dumps([r.model_dump(mode="json") for r in requests]), order_id))

    def purchase_requests(self, order_id):
        with self._connection() as db:
            row = db.execute("SELECT requests_json FROM execution WHERE order_id=?", (order_id,)).fetchone()
            return ([PurchaseRequest.model_validate_json(json.dumps(r)) for r in json.loads(row[0])]
                    if row[0] else None)

    def save_assignment(self, order_id, quotes: list[Quote], *, simulated=False):
        self._require_purchase_execution()
        with self._connection(write=True) as db:
            if not self._owns_reservations(db, order_id):
                raise ValueError("Snapshot is not executable")
            if db.execute("SELECT 1 FROM suborders WHERE order_id=?", (order_id,)).fetchone():
                raise ValueError("Allocation already persisted")
            for q in quotes:
                db.execute("INSERT INTO suborders(id,order_id,store_id,state,result,quote_json,total_cents) "
                           "VALUES (?,?,?,'preparado',?,?,?)",
                           (str(uuid4()), order_id, q.store_id, "simulado" if simulated else None,
                            q.model_dump_json(), q.total_cents))
            db.execute("UPDATE execution SET state=? WHERE order_id=?",
                       ("simulado" if simulated else "preparado", order_id))
            if simulated:
                db.execute("DELETE FROM reservations WHERE order_id=?", (order_id,))
                self._notice(db, order_id, "Resultado simulado: no se ha comprado ni modificado el carrito.")

    def suborders(self, order_id):
        with self._connection() as db:
            return [dict(r) for r in db.execute("SELECT * FROM suborders WHERE order_id=? ORDER BY rowid",
                                              (order_id,))]

    def refresh_quote(self, order_id, quote):
        self._require_purchase_execution()
        with self._connection(write=True) as db:
            changed = db.execute("UPDATE suborders SET quote_json=?,total_cents=? WHERE order_id=? "
                                 "AND store_id=? AND state='preparado' AND result IS NULL",
                                 (quote.model_dump_json(), quote.total_cents, order_id, quote.store_id)).rowcount
            if not changed:
                raise ValueError("Suborder is not refreshable")
            self._notice(db, order_id, f"Precio actualizado: {quote.total_cents} céntimos, entrega {quote.delivery}.")

    def save_attempt(self, order_id: str, store_id: str, cart: PreparedCart) -> str:
        self._require_purchase_execution()
        with self._connection(write=True) as db:
            if not self._owns_reservations(db, order_id):
                raise ValueError("Snapshot is not executable")
            row = db.execute("SELECT * FROM suborders WHERE order_id=? AND store_id=?",
                             (order_id, store_id)).fetchone()
            if (row is None or row["state"] != "preparado" or row["result"] is not None
                    or row["awaiting_resume"]):
                raise ValueError("Suborder not ready")
            if (cart.fingerprint != cart_fingerprint(cart.quote)
                    or cart.fingerprint != cart_fingerprint(Quote.model_validate_json(row["quote_json"]))):
                raise ValueError("Cart does not match the durable allocation")
            if db.execute("SELECT 1 FROM attempts WHERE suborder_id=? AND settled=0",
                          (row["id"],)).fetchone():
                raise ValueError("Unresolved attempt")
            attempt = str(uuid4())
            db.execute("INSERT INTO attempts(id,suborder_id,fingerprint,cart_json) VALUES (?,?,?,?)",
                       (attempt, row["id"], cart.fingerprint, cart.model_dump_json()))
            db.execute("UPDATE suborders SET state='enviando' WHERE id=?", (row["id"],))
            db.execute("UPDATE execution SET state='enviando' WHERE order_id=?", (order_id,))
            return attempt

    def attempt_order(self, attempt_id):
        with self._connection() as db:
            return db.execute("SELECT s.order_id FROM attempts a JOIN suborders s ON s.id=a.suborder_id "
                              "WHERE a.id=?", (attempt_id,)).fetchone()[0]

    def uncertain_attempts(self) -> list[tuple[str, PreparedCart]]:
        with self._connection() as db:
            return [(r[0], PreparedCart.model_validate_json(r[1])) for r in db.execute(
                "SELECT id,cart_json FROM attempts WHERE settled=0 AND cart_json IS NOT NULL ORDER BY rowid")]

    def record_submission(self, attempt_id: str, result: Submission) -> None:
        self._require_purchase_execution()
        with self._connection(write=True) as db:
            row = db.execute("SELECT a.*,s.order_id FROM attempts a JOIN suborders s ON s.id=a.suborder_id "
                             "WHERE a.id=?", (attempt_id,)).fetchone()
            if row is None:
                raise KeyError(attempt_id)
            if row["settled"]:
                return
            cart = PreparedCart.model_validate_json(row["cart_json"])
            if result.status == "confirmed" and (not result.external_id or not result.external_id.strip()
                    or result.total_cents != cart.quote.total_cents or not result.delivery):
                result = Submission(status="uncertain", reason="confirmation evidence incomplete")
            if row["evidence_json"] == result.model_dump_json():
                return
            state = {"confirmed": "confirmado", "uncertain": "resultado_incierto",
                     "requires_intervention": "requiere_intervencion", "failed": "fallido"}[result.status]
            # Even a failed submit needs reconciliation before another final action.
            db.execute("UPDATE attempts SET evidence_json=?,settled=? WHERE id=?",
                       (result.model_dump_json(), int(result.status == "confirmed"), attempt_id))
            db.execute("UPDATE suborders SET state=?,result=?,external_id=? WHERE id=?",
                       (state, "confirmado" if result.status == "confirmed" else None,
                        result.external_id, row["suborder_id"]))
            oid = row["order_id"]
            subs = db.execute("SELECT * FROM suborders WHERE order_id=?", (oid,)).fetchall()
            if result.status == "confirmed":
                for snapshot in db.execute("SELECT line_json FROM order_lines WHERE order_id=?", (oid,)):
                    line = json.loads(snapshot[0])
                    allocations = [s for s in subs if any(i.line_id == line["id"] for i in
                                   Quote.model_validate_json(s["quote_json"]).items)]
                    if allocations and all(s["state"] == "confirmado" for s in allocations):
                        db.execute("DELETE FROM list_lines WHERE id=? AND revision=?",
                                   (line["id"], line["revision"]))
                        db.execute("DELETE FROM reservations WHERE line_id=? AND order_id=?", (line["id"], oid))
            states = {s["state"] for s in subs}
            aggregate = next((s for s in ("resultado_incierto", "requiere_intervencion", "fallido",
                                         "enviando", "preparado") if s in states), "confirmado")
            db.execute("UPDATE execution SET state=? WHERE order_id=?", (aggregate, oid))
            self._notice(db, oid, f"Tienda {cart.quote.store_id}: {state}. " +
                         (f"Referencia externa: {result.external_id}; total {result.total_cents} céntimos."
                          if state == "confirmado" else "No se repetirá la compra sin reconciliar."))

    def definitely_not_submitted(self, attempt_id):
        self._require_purchase_execution()
        with self._connection(write=True) as db:
            row = db.execute("SELECT a.suborder_id,s.order_id FROM attempts a JOIN suborders s "
                             "ON s.id=a.suborder_id WHERE a.id=? AND a.settled=0", (attempt_id,)).fetchone()
            if row:
                db.execute("UPDATE attempts SET settled=1 WHERE id=?", (attempt_id,))
                db.execute("UPDATE suborders SET state='requiere_intervencion',awaiting_resume=1 WHERE id=?", (row[0],))
                db.execute("UPDATE execution SET state='requiere_intervencion' WHERE order_id=?", (row[1],))
                self._notice(db, row[1], "Verificado: no se envió la compra. Solicita reanudar para cotizar de nuevo.")

    def finish_resume(self, order_id):
        self._require_purchase_execution()
        with self._connection(write=True) as db:
            pending = db.execute("SELECT 1 FROM attempts a JOIN suborders s ON s.id=a.suborder_id "
                                 "WHERE s.order_id=? AND a.settled=0", (order_id,)).fetchone()
            requested = db.execute("SELECT resume_requested FROM execution WHERE order_id=?", (order_id,)).fetchone()
            if not pending and requested[0] and self._owns_reservations(db, order_id):
                db.execute("UPDATE suborders SET awaiting_resume=0,state='preparado' "
                           "WHERE order_id=? AND awaiting_resume=1", (order_id,))
                db.execute("UPDATE execution SET state='pendiente' WHERE order_id=? "
                           "AND resume_requested=1 AND state NOT IN ('confirmado','simulado')", (order_id,))
            db.execute("UPDATE execution SET resume_requested=0 WHERE order_id=?", (order_id,))
