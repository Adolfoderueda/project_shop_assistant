"""Short SQLite transactions. No network or browser operations belong here."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from catalog import PRODUCT_RULES
from domain import IncomingMessage, Intent, ListLine, Order, Reply


class Repository:
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
            if version > 1:
                raise ValueError("Database schema is newer than this application")
            if version == 0:
                db.executescript((Path(__file__).parent / "migrations/001.sql").read_text())
            db.executemany(
                "INSERT OR IGNORE INTO products VALUES (?, ?)",
                [(r.id, r.model_dump_json()) for r in PRODUCT_RULES],
            )

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

    def apply_intent(self, update_id: int, intent: Intent, mode: str) -> Reply:
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
        if intent.action == "add":
            if not intent.lines or any(not line.description for line in intent.lines):
                return Reply(text="Indica qué producto quieres añadir.")
            for line in intent.lines:
                db.execute(
                    "INSERT INTO list_lines VALUES (?,NULL,?,?,1,?)",
                    (str(uuid4()), line.description, line.quantity, update_id),
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
                if None in selected or not selected.issubset({line.id for line in lines}):
                    return Reply(text="Selecciona líneas existentes antes de comprar.")
                lines = [line for line in lines if line.id in selected]
                # Do not silently reinterpret quantities supplied with a selection.
                quantities = {line.line_id: line.quantity for line in intent.lines}
                if any(quantities[l.id] not in (None, l.quantity) for l in lines):
                    return Reply(text="Actualiza las cantidades de la lista antes de comprar.")
            if not lines or any(line.quantity is None for line in lines):
                return Reply(text="Indica productos y cantidades antes de comprar.")
            order_id = str(uuid4())
            db.execute(
                "INSERT INTO orders(id,mode,source_update_id) VALUES (?,?,?)",
                (order_id, mode, update_id),
            )
            db.executemany(
                "INSERT INTO order_lines VALUES (?,?,?)",
                [(order_id, i, line.model_dump_json()) for i, line in enumerate(lines)],
            )
            return Reply(text="Orden registrada; todavía no se ha comprado.", order_id=order_id)
        if intent.action == "list":
            return Reply(
                text="\n".join(
                    f"{l.description}: {l.quantity if l.quantity else '?'}" for l in self._lines(db)
                )
                or "La lista está vacía."
            )
        return Reply(
            text=intent.question or "La operación requiere al coordinador.",
            order_id=intent.order_id,
        )
