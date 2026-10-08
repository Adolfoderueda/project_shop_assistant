"""Short SQLite transactions. No network or browser operations belong here."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from catalog import PRODUCT_RULES, resolve_product
from checkout_storage import CheckoutRepository
from dialogue import expired
from dialogue_storage import DialogueRepository
from domain import IncomingMessage, Intent, IntentLine, ListLine, Order, Reply
from presentation_storage import PresentationRepository
from product_memory import (
    ObservedProduct,
    _record_missing_product,
    identifiable_product_name,
    matches_observation,
)

OBSERVED_PRODUCTS = (
    ("amascotados-alpha-spirit-wild-fish-12kg", "amascotados", "dog-food",
     "Alpha Spirit Wild Fish 12 Kg",
     "https://www.amascotados.com/alpha-spirit/2883-alpha-spirit-seco-only-fish-12-kg-8436586310295.html",
     "2026-09-27", 6399, True, "12 kg; GTIN no verificado independientemente"),
    ("charro-blemil-optimum-evolution-1-800g", "charro", "formula",
     "Blemil Optimum Evolution 1 800 g",
     "https://www.charrodesdecasa.com/leches/20209-blemil-optimum-evolution-1-800-gr-8426594127534.html",
     "2026-09-27", 2515, None, "800 g; referencia no verificada"),
    ("nappy-dodot-talla-3-186", "nappy", "diapers", "Dodot talla 3 186 unidades",
     "https://nappy.es/dodot/6035-panales-talla-3-bebe-seco-dodot.html",
     "2026-09-27", 4687, True, "186 unidades"),
    ("mercadona-dodot-sensitive-talla-3-56", "mercadona", "diapers",
     "Dodot Sensitive talla 3 paquete 56",
     "https://tienda.mercadona.es/product/52879/panales-bebe-talla-3-6-10-kg-dodot-sensitive-paquete",
     "2026-09-28", 1695, None, "56 unidades; CP 28023"),
)


class Repository(CheckoutRepository, DialogueRepository, PresentationRepository):
    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def _connection(self, *, write=False):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def migrate(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 7:
                raise ValueError("Database schema is newer than this application")
            if version == 0:
                db.executescript((Path(__file__).parent / "migrations/001.sql").read_text())
            if version < 2:
                db.executescript((Path(__file__).parent / "migrations/002.sql").read_text())
            if version < 3:
                db.executescript((Path(__file__).parent / "migrations/003.sql").read_text())
            if version < 4:
                db.executescript((Path(__file__).parent / "migrations/004.sql").read_text())
            if version < 5:
                db.executescript((Path(__file__).parent / "migrations/005.sql").read_text())
            if version < 6:
                db.executescript((Path(__file__).parent / "migrations/006.sql").read_text())
            if version < 7:
                db.executescript((Path(__file__).parent / "migrations/007.sql").read_text())
            db.executemany(
                "INSERT OR IGNORE INTO observed_products "
                "(id,store_id,product_id,title,url,observed_on,price_cents,availability,format_note) "
                "VALUES (?,?,?,?,?,?,?,?,?)", OBSERVED_PRODUCTS,
            )
            db.executemany(
                "INSERT OR IGNORE INTO products VALUES (?, ?)",
                [(r.id, r.model_dump_json()) for r in PRODUCT_RULES],
            )

    def find_products(self, query: str, limit: int = 5) -> list[ObservedProduct]:
        with self._connection() as db:
            return self._find_products(db, query, limit)

    @staticmethod
    def _find_products(db, query: str, limit: int = 5) -> list[ObservedProduct]:
        if limit <= 0:
            return []
        results = []
        for row in db.execute(
            "SELECT id,store_id,product_id,title,url,observed_on,price_cents,"
            "availability,format_note FROM observed_products ORDER BY id"
        ):
            values = dict(row)
            if values["availability"] is not None:
                values["availability"] = bool(values["availability"])
            product = ObservedProduct(**values)
            if matches_observation(query, product):
                results.append(product)
                if len(results) == limit:
                    break
        return results

    def product_requests(self) -> list[str]:
        with self._connection() as db:
            return [row[0] for row in db.execute("SELECT name FROM product_requests ORDER BY name")]

    def assert_authorized_owner(self, user_id: int) -> None:
        """Fail closed on retained work from another identity before recovery or dispatch."""
        if type(user_id) is not int or user_id <= 0:
            raise PermissionError("Invalid owner identity")
        with self._connection() as db:
            foreign_inbox = db.execute(
                "SELECT 1 FROM inbox WHERE user_id!=? OR chat_id!=? LIMIT 1",
                (user_id, user_id)).fetchone()
            foreign_notices = db.execute(
                "SELECT 1 FROM outbox WHERE chat_id!=? LIMIT 1", (user_id,)).fetchone()
            missing_source = db.execute(
                "SELECT 1 FROM orders o LEFT JOIN inbox i ON i.update_id=o.source_update_id "
                "WHERE i.update_id IS NULL LIMIT 1").fetchone()
            foreign_dialogue = db.execute(
                "SELECT 1 FROM dialogue_state WHERE user_id!=? OR chat_id!=? "
                "OR user_id IS NULL OR chat_id IS NULL LIMIT 1", (user_id, user_id),
            ).fetchone()
            if foreign_inbox or foreign_notices or missing_source or foreign_dialogue:
                raise PermissionError("Stored work belongs to another owner; manual review required")
            for row in db.execute("SELECT update_id,user_id,chat_id FROM presentation_jobs"):
                if (row["user_id"], row["chat_id"]) != (user_id, user_id):
                    raise PermissionError("Stored work belongs to another owner; manual review required")
                self._read_prepared(db, row["update_id"])

    def verify_formula(self, gtin: str) -> None:
        """Persist a manually cross-checked reference, without changing the baked-in catalog."""
        from domain import ProductRule
        with self._connection(write=True) as db:
            row = db.execute("SELECT rule_json FROM products WHERE id='formula'").fetchone()
            if row is None:
                raise ValueError("Formula rule missing")
            rule = ProductRule.model_validate_json(row[0])
            if (rule.brand, rule.variant, rule.stage) != ("Blemil", "Evolution", 1):
                raise ValueError("Formula restriction changed; manual review required")
            db.execute("UPDATE products SET rule_json=? WHERE id='formula'",
                       (rule.model_copy(update={"gtin": gtin, "verified": True}).model_dump_json(),))

    def ingest_batch(self, messages: list[IncomingMessage], next_offset: int) -> None:
        if type(next_offset) is not int or next_offset < 0:
            raise ValueError("Invalid offset")
        if any(m.update_id >= next_offset for m in messages):
            raise ValueError("Offset must follow the batch")
        with self._connection(write=True) as db:
            db.executemany(
                "INSERT OR IGNORE INTO inbox(update_id,user_id,chat_id,text) VALUES (?,?,?,?)",
                [(m.update_id, m.user_id, m.chat_id, m.text) for m in messages],
            )
            db.execute(
                "UPDATE meta SET value=max(value,?) WHERE key='telegram_offset'", (next_offset,)
            )

    def telegram_offset(self) -> int:
        with self._connection() as db:
            return db.execute("SELECT value FROM meta WHERE key='telegram_offset'").fetchone()[0]

    def pending_messages(self) -> list[IncomingMessage]:
        with self._connection() as db:
            return [
                IncomingMessage(**dict(row))
                for row in db.execute(
                    "SELECT update_id,user_id,chat_id,text FROM inbox WHERE completed=0 ORDER BY update_id"
                )
            ]

    def pending_notices(self) -> list[tuple[str, int, str]]:
        with self._connection() as db:
            return [
                (row["id"], row["chat_id"], Reply.model_validate_json(row["reply_json"]).text)
                for row in db.execute(
                    "SELECT id,chat_id,reply_json FROM outbox WHERE sent_at IS NULL ORDER BY rowid"
                )
            ]

    def mark_notice_sent(self, id: str) -> None:
        with self._connection(write=True) as db:
            db.execute(
                "UPDATE outbox SET sent_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE id=? AND sent_at IS NULL", (id,),
            )

    @staticmethod
    def _lines(db) -> list[ListLine]:
        return [
            ListLine(**dict(row))
            for row in db.execute(
                "SELECT id,product_id,description,quantity,revision FROM list_lines ORDER BY rowid"
            )
        ]

    def list_lines(self) -> list[ListLine]:
        with self._connection() as db:
            return self._lines(db)

    def get_order(self, order_id: str) -> Order:
        with self._connection() as db:
            row = db.execute("SELECT id,mode FROM orders WHERE id=?", (order_id,)).fetchone()
            if row is None:
                raise KeyError(order_id)
            lines = [
                ListLine.model_validate_json(r[0])
                for r in db.execute(
                    "SELECT line_json FROM order_lines WHERE order_id=? ORDER BY position",
                    (order_id,),
                )
            ]
            return Order(**dict(row), lines=lines)

    def message_result(self, update_id: int) -> tuple[IncomingMessage, Reply | None]:
        with self._connection() as db:
            row = db.execute("SELECT * FROM inbox WHERE update_id=?", (update_id,)).fetchone()
            if row is None:
                raise KeyError(update_id)
            return (
                IncomingMessage(**{k: row[k] for k in ("update_id", "user_id", "chat_id", "text")}),
                Reply.model_validate_json(row["reply_json"]) if row["completed"] else None,
            )

    def pending_clarification(self, user_id: int) -> Intent | None:
        with self._connection() as db:
            revisions = {l.id: l.revision for l in self._lines(db)}
            for row in db.execute("SELECT chat_id FROM dialogue_state WHERE user_id=?", (user_id,)):
                state = self._read_dialogue_state(db, user_id, row[0])
                if state is None or expired(state, datetime.now(UTC)):
                    continue
                refs = (*state.candidates, *((state.target,) if state.target else ()))
                if any(revisions.get(r.id) != r.revision for r in refs):
                    continue
                if state.question == "quantity" and state.target:
                    return Intent(action="set_quantity", lines=[IntentLine(line_id=state.target.id)])
                if state.question == "remove_id":
                    return Intent(action="remove", lines=[IntentLine(line_id=r.id) for r in state.candidates])
            return None

    def apply_intent(
        self, update_id: int, intent: Intent, mode: str, *, conversation=False
    ) -> Reply:
        if conversation:
            return self.apply_dialogue(update_id, intent, mode, now=datetime.now(UTC))
        if mode not in ("dry_run", "live"):
            raise ValueError("Invalid mode")
        with self._connection(write=True) as db:
            source = db.execute("SELECT * FROM inbox WHERE update_id=?", (update_id,)).fetchone()
            if source is None:
                raise KeyError(update_id)
            if source["completed"]:
                return Reply.model_validate_json(source["reply_json"])
            reply = self._apply(db, update_id, intent, mode)
            payload = reply.model_dump_json()
            db.execute(
                "UPDATE inbox SET completed=1,reply_json=? WHERE update_id=?", (payload, update_id)
            )
            db.execute(
                "INSERT INTO outbox(id,update_id,chat_id,reply_json) VALUES (?,?,?,?)",
                (str(uuid4()), update_id, source["chat_id"], payload),
            )
            return reply

    def _apply(self, db, update_id, intent, mode):
        if intent.action == "product_query":
            if (len(intent.lines) != 1 or not intent.lines[0].description
                    or intent.lines[0].line_id is not None
                    or intent.lines[0].quantity is not None
                    or intent.lines[0].url is not None):
                return Reply(text="Aclara el producto que buscas.")
            name = intent.lines[0].description
            if not identifiable_product_name(name):
                return Reply(text="Aclara el producto que buscas.")
            # Read from this same transaction, not an earlier model context snapshot.
            products = self._find_products(db, name)
            if not products:
                _record_missing_product(db, name)
                return Reply(text=f"No tenemos ficha observada de {name}; lo he anotado para revisar.")
            details = []
            for product in products:
                price = (f"{product.price_cents // 100},{product.price_cents % 100:02d} €"
                         if product.price_cents is not None else "precio no observado")
                stock = ("stock no observado" if product.availability is None
                         else "stock observado disponible" if product.availability
                         else "stock observado no disponible")
                details.append(
                    f"{product.title} — fuente {product.store_id} ({product.url}); "
                    f"observado {product.observed_on}; "
                    f"precio observado {price}; {stock}; "
                    f"{product.format_note or 'sin detalle de formato'}"
                )
            return Reply(text="\n".join(details) + "\nDatos históricos: precio y stock no actuales.")
        if intent.action == "add":
            if not intent.lines or any(not line.description for line in intent.lines):
                return Reply(text="Indica qué producto quieres añadir.")
            for line in intent.lines:
                db.execute(
                    "INSERT INTO list_lines VALUES (?,?,?,?,1,?)",
                    (
                        str(uuid4()),
                        resolve_product(line.description),
                        line.description,
                        line.quantity,
                        update_id,
                    ),
                )
            return Reply(text="Añadido a la lista.")
        if intent.action in ("remove", "set_quantity"):
            existing = {line.id for line in self._lines(db)}
            if not intent.lines or any(line.line_id not in existing for line in intent.lines):
                return Reply(text="Indica una línea existente.")
            if intent.action == "set_quantity" and any(l.quantity is None for l in intent.lines):
                return Reply(text="Indica la cantidad.")
            for line in intent.lines:
                if intent.action == "remove":
                    db.execute("DELETE FROM list_lines WHERE id=?", (line.line_id,))
                else:
                    db.execute(
                        "UPDATE list_lines SET quantity=?,revision=revision+1 WHERE id=?",
                        (line.quantity, line.line_id),
                    )
            return Reply(text="Lista actualizada.")
        if intent.action == "buy":
            lines = self._lines(db)
            if intent.lines:
                selected = {line.line_id for line in intent.lines}
                if len(selected) != len(intent.lines):
                    return Reply(text="Selecciona cada línea una sola vez antes de comprar.")
                if None in selected or not selected.issubset({line.id for line in lines}):
                    return Reply(text="Selecciona líneas existentes antes de comprar.")
                lines = [line for line in lines if line.id in selected]
                # Do not silently reinterpret quantities supplied with a selection.
                quantities = {line.line_id: line.quantity for line in intent.lines}
                if any(quantities[l.id] not in (None, l.quantity) for l in lines):
                    return Reply(text="Actualiza las cantidades de la lista antes de comprar.")
            if not lines or any(line.quantity is None for line in lines):
                return Reply(text="Indica productos y cantidades antes de comprar.")
            if any(db.execute("SELECT 1 FROM reservations WHERE line_id=?", (l.id,)).fetchone()
                   for l in lines):
                return Reply(text="Hay líneas reservadas por una orden pendiente; consulta su estado.")
            order_id = str(uuid4())
            db.execute(
                "INSERT INTO orders(id,mode,source_update_id) VALUES (?,?,?)",
                (order_id, mode, update_id),
            )
            db.executemany(
                "INSERT INTO order_lines VALUES (?,?,?)",
                [(order_id, i, line.model_dump_json()) for i, line in enumerate(lines)],
            )
            db.execute("INSERT INTO execution(order_id) VALUES (?)", (order_id,))
            db.executemany("INSERT INTO reservations VALUES (?,?)",
                           [(l.id, order_id) for l in lines])
            return Reply(text="Orden registrada; todavía no se ha comprado.", order_id=order_id)
        if intent.action in ("status", "resume"):
            row = db.execute("SELECT state,legacy_quarantined FROM execution WHERE order_id=?",
                             (intent.order_id,)).fetchone()
            if row is None:
                return Reply(text="Indica una orden existente.")
            if intent.action == "resume" and row["legacy_quarantined"]:
                return Reply(text="Orden antigua en cuarentena: reanudar no autoriza ejecutar esta instantánea. "
                             "Se requiere revisar los conflictos y las compras anteriores.", order_id=intent.order_id)
            if intent.action == "resume" and row[0] not in ("confirmado", "simulado"):
                db.execute("UPDATE execution SET resume_requested=1 WHERE order_id=?",
                           (intent.order_id,))
                return Reply(text="Reanudación solicitada; primero se reconciliará, sin repetir la compra.",
                             order_id=intent.order_id)
            subs = db.execute(
                "SELECT store_id,state,result,external_id,total_cents,quote_json "
                "FROM suborders WHERE order_id=? ORDER BY rowid", (intent.order_id,)
            ).fetchall()
            details = []
            allocations = {}
            for sub in subs:
                quote = json.loads(sub["quote_json"]) if sub["quote_json"] else {}
                state = "simulado" if sub["result"] == "simulado" else sub["state"]
                detail = f"{sub['store_id']}: {state}"
                if state == "confirmado":
                    detail += f"; referencia {sub['external_id']}; total {sub['total_cents']} centimos"
                for item in quote.get("items", []):
                    allocations.setdefault(item["line_id"], []).append((state, item))
                details.append(detail)
            snapshots = [json.loads(r[0]) for r in db.execute(
                "SELECT line_json FROM order_lines WHERE order_id=? ORDER BY position",
                (intent.order_id,))]
            unresolved = [line for line in snapshots if not allocations.get(line["id"])
                          or any(state != "confirmado" for state, _ in allocations[line["id"]])]
            if unresolved:
                details.append("Lineas sin resolver: " + ", ".join(
                    line["id"] for line in unresolved))
            return Reply(text="\n".join([f"Estado: {row[0]}", *details]), order_id=intent.order_id)
        if intent.action == "list":
            return Reply(
                text="\n".join(
                    f"{l.id} — {l.description}: {l.quantity if l.quantity else '?'}"
                    for l in self._lines(db)
                )
                or "La lista está vacía."
            )
        return Reply(
            text=intent.question or "La operación requiere al coordinador.",
            order_id=intent.order_id,
        )
