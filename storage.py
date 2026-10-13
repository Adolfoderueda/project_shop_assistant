"""Short SQLite transactions. No network or browser operations belong here."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from catalog import PRODUCT_RULES, resolve_product
from checkout_storage import CheckoutRepository
from dialogue import expired
from dialogue_storage import DialogueRepository
from domain import (
    IncomingCallback,
    IncomingEvent,
    IncomingMessage,
    Intent,
    IntentLine,
    ListLine,
    Order,
    Reply,
    decode_event,
)
from presentation_storage import PresentationRepository
from product_memory import (
    ObservedProduct,
    _record_missing_product,
    identifiable_product_name,
    matches_observation,
)
from shopping_agent.guided_storage import GuidedRepository
from shopping_agent.storage import AgentRepository

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


class Repository(CheckoutRepository, DialogueRepository, PresentationRepository, GuidedRepository, AgentRepository):
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
            if version > 10:
                raise ValueError("Database schema is newer than this application")
            # executescript commits a pending transaction first. Execute complete SQL
            # statements ourselves so DDL, data and user_version roll back together.
            db.execute("BEGIN IMMEDIATE")
            for target in range(version + 1, 11):
                script = files('migrations').joinpath(f'{target:03}.sql').read_text(encoding='utf-8')
                statement = ''
                for line in script.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        if statement.strip().upper() not in {'BEGIN;', 'BEGIN IMMEDIATE;', 'COMMIT;'}:
                            db.execute(statement)
                        statement = ''
                if statement.strip():
                    raise ValueError('Incomplete migration SQL')
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
            for table in ('agent_proposals', 'conversation_routes'):
                if db.execute(f'SELECT 1 FROM {table} WHERE user_id!=? OR chat_id!=? LIMIT 1',
                              (user_id, user_id)).fetchone():
                    raise PermissionError('Stored agent work belongs to another owner')
            for row in db.execute('SELECT * FROM conversation_routes WHERE command_update_id IS NOT NULL'):
                try:
                    if self._command_origin(db, row['user_id'], row['chat_id']) is None:
                        raise ValueError('Invalid command provenance')
                except (ValueError, KeyError) as error:
                    raise PermissionError('Invalid retained command provenance') from error
            for row in db.execute('SELECT * FROM agent_proposals'):
                try:
                    proposal = json.loads(row['proposal_json'])
                    source = self._agent_source(db, proposal['source_update_id'])
                    if ((source['user_id'], source['chat_id']) != (user_id, user_id)
                            or self._agent_snapshot(db, source).proposal is None):
                        raise ValueError('Invalid retained proposal')
                except (ValueError, KeyError, TypeError) as error:
                    raise PermissionError('Invalid retained agent provenance') from error
            for row in db.execute("SELECT update_id,user_id,chat_id FROM presentation_jobs"):
                if (row["user_id"], row["chat_id"]) != (user_id, user_id):
                    raise PermissionError("Stored work belongs to another owner; manual review required")
                self._read_prepared(db, row["update_id"])
            self._assert_guided_owner(db, user_id)

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

    def _assert_guided_owner(self, db, user_id):
        from shopping_agent.guided_contracts import GuidedQuestion, PendingTopic

        try:
            for row in db.execute('SELECT * FROM inbox'):
                self._stored_event(row)
            questions = {}
            for table, column, model in (
                ('guided_questions', 'question_json', GuidedQuestion),
                ('guided_topics', 'topic_json', PendingTopic),
            ):
                for row in db.execute(f'SELECT * FROM {table}'):
                    if (row['user_id'], row['chat_id']) != (user_id, user_id):
                        raise ValueError('Foreign guided state')
                    state = model.model_validate_json(row[column])
                    if (str(state.id), state.version, state.source_update_id) != (
                            row['id'], row['version'], row['source_update_id']):
                        raise ValueError('Guided state metadata mismatch')
                    source = db.execute('SELECT * FROM inbox WHERE update_id=?',
                                        (state.source_update_id,)).fetchone()
                    if (source is None or (source['user_id'], source['chat_id']) != (user_id, user_id)
                            or not source['completed']):
                        raise ValueError('Orphan guided source')
                    self._stored_event(source)
                    if table == 'guided_questions':
                        if (state.owner_id, state.chat_id) != (user_id, user_id):
                            raise ValueError('Foreign question payload')
                        notice = db.execute('SELECT * FROM outbox WHERE id=?',
                                            (row['notice_id'],)).fetchone()
                        if (notice is None or notice['chat_id'] != user_id
                                or notice['update_id'] != state.source_update_id
                                or notice['reply_json'] != source['reply_json']
                                or self._guided_question_row(db, row) != state):
                            raise ValueError('Question notice mismatch')
                        questions[(row['id'], row['version'])] = (state, row['notice_id'])
                    else:
                        event = self._stored_event(source)
                        proposal = self._agent_snapshot(db, source).proposal
                        if (not isinstance(event, IncomingMessage) or event.text != state.original_text
                                or proposal is None or (proposal.id, proposal.revision) !=
                                (state.proposal_id, state.proposal_revision)
                                or state.expires_at > proposal.expires_at):
                            raise ValueError('Topic provenance mismatch')
            for row in db.execute('SELECT * FROM guided_tokens'):
                self._guided_token_row(db, row)
                question, notice_id = questions[(row['question_id'], row['question_version'])]
                if ((row['user_id'], row['chat_id']) != (user_id, user_id)
                        or row['notice_id'] != notice_id
                        or not 0 <= row['choice_index'] < len(question.choices)):
                    raise ValueError('Token binding mismatch')
                reply = Reply.model_validate_json(db.execute(
                    'SELECT reply_json FROM outbox WHERE id=?', (notice_id,)).fetchone()[0])
                buttons = ([button for buttons in reply.keyboard.rows for button in buttons]
                           if reply.keyboard else [])
                if (len(buttons) != len(question.choices)
                        or buttons[row['choice_index']].token != row['token']
                        or buttons[row['choice_index']].label
                        != question.choices[row['choice_index']].label):
                    raise ValueError('Token not offered in its notice')
                if row['consumed_update_id'] is not None:
                    source = db.execute('SELECT * FROM inbox WHERE update_id=?',
                                        (row['consumed_update_id'],)).fetchone()
                    result = Reply.model_validate_json(row['result_json'])
                    if (source is None or (source['user_id'], source['chat_id']) != (user_id, user_id)
                            or not source['completed']
                            or Reply.model_validate_json(source['reply_json']) != result):
                        raise ValueError('Token result source mismatch')
                    self._stored_event(source)
                elif row['result_json'] is not None:
                    raise ValueError('Orphan token result')
            for row in db.execute('SELECT * FROM telegram_deliveries'):
                if row['chat_id'] != user_id:
                    raise ValueError('Foreign delivery')
                self._delivery_notice(db, row['notice_id'], row['chat_id'],
                                      row['message_id'], row['digest'])
        except (ValueError, KeyError, TypeError, IndexError) as error:
            raise PermissionError('Invalid retained guided provenance') from error

    def ingest_batch(self, messages: list[IncomingMessage], next_offset: int) -> None:
        if any(not isinstance(message, IncomingMessage) for message in messages):
            raise ValueError('Legacy batch cannot contain callback events')
        self.ingest_events(messages, next_offset)

    @staticmethod
    def _stored_event(row) -> IncomingEvent:
        if 'kind' not in tuple(row.keys()):
            return IncomingMessage(**{k: row[k] for k in ('update_id', 'user_id', 'chat_id', 'text')})
        if row['kind'] == 'message':
            event = IncomingMessage(**{k: row[k] for k in ('update_id', 'user_id', 'chat_id', 'text')})
            if row['callback_query_id'] is not None or row['callback_ack_state'] is not None:
                raise ValueError('Invalid message metadata')
        elif row['kind'] == 'callback':
            event = decode_event(json.loads(row['payload_json']))
            if (not isinstance(event, IncomingCallback) or row['text'] != ''
                    or event.callback_query_id != row['callback_query_id']
                    or row['callback_ack_state'] not in {'pending', 'sent', 'expired'}):
                raise ValueError('Invalid callback metadata')
        else:
            raise ValueError('Unknown stored event kind')
        if (event.update_id, event.user_id, event.chat_id) != (
                row['update_id'], row['user_id'], row['chat_id']):
            raise ValueError('Stored event identity mismatch')
        if row['payload_json'] is not None and decode_event(json.loads(row['payload_json'])) != event:
            raise ValueError('Stored event payload mismatch')
        return event

    @staticmethod
    def _agent_message(source):
        if 'kind' in tuple(source.keys()) and source['kind'] != 'message':
            raise ValueError('A callback is not executable message text')
        return Repository._stored_event(source)

    def _apply_dialogue(self, db, source, proposal, mode, *, now):
        self._agent_message(source)
        return super()._apply_dialogue(db, source, proposal, mode, now=now)

    def ingest_events(self, events: list[IncomingEvent], next_offset: int) -> None:
        if type(next_offset) is not int or next_offset < 0:
            raise ValueError("Invalid offset")
        events = [decode_event(event.model_dump(mode='json')) for event in events]
        if any(event.update_id >= next_offset for event in events):
            raise ValueError("Offset must follow the batch")
        with self._connection(write=True) as db:
            typed_inbox = 'kind' in {row[1] for row in db.execute('PRAGMA table_info(inbox)')}
            for event in events:
                existing = db.execute('SELECT * FROM inbox WHERE update_id=?',
                                      (event.update_id,)).fetchone()
                if existing is not None:
                    if self._stored_event(existing) != event:
                        raise ValueError('Conflicting update replay')
                    continue
                callback = isinstance(event, IncomingCallback)
                if not typed_inbox:
                    if callback:
                        raise ValueError('A callback requires schema v10')
                    db.execute('INSERT INTO inbox(update_id,user_id,chat_id,text) VALUES (?,?,?,?)',
                               (event.update_id, event.user_id, event.chat_id, event.text))
                    continue
                if callback:
                    existing = db.execute('SELECT * FROM inbox WHERE callback_query_id=?',
                                          (event.callback_query_id,)).fetchone()
                    if existing is not None:
                        original = self._stored_event(existing)
                        if (original.model_dump(exclude={'update_id'})
                                != event.model_dump(exclude={'update_id'})):
                            raise ValueError('Conflicting callback query replay')
                        continue
                db.execute(
                    'INSERT INTO inbox(update_id,user_id,chat_id,text,kind,payload_json,'
                    'callback_query_id,callback_ack_state) VALUES (?,?,?,?,?,?,?,?)',
                    (event.update_id, event.user_id, event.chat_id, '' if callback else event.text,
                     'callback' if callback else 'message', event.model_dump_json(),
                     event.callback_query_id if callback else None, 'pending' if callback else None))
            db.execute(
                "UPDATE meta SET value=max(value,?) WHERE key='telegram_offset'", (next_offset,)
            )

    def telegram_offset(self) -> int:
        with self._connection() as db:
            return db.execute("SELECT value FROM meta WHERE key='telegram_offset'").fetchone()[0]

    def pending_messages(self) -> list[IncomingMessage]:
        return [event for event in self.pending_events() if isinstance(event, IncomingMessage)]

    def pending_events(self) -> list[IncomingEvent]:
        with self._connection() as db:
            return [self._stored_event(row) for row in db.execute(
                'SELECT * FROM inbox WHERE completed=0 ORDER BY update_id')]

    def pending_replies(self) -> list[tuple[str, int, Reply]]:
        with self._connection() as db:
            return [(row['id'], row['chat_id'], Reply.model_validate_json(row['reply_json']))
                    for row in db.execute('SELECT id,chat_id,reply_json FROM outbox '
                                          'WHERE sent_at IS NULL ORDER BY rowid')]

    def pending_callback_acks(self) -> list[str]:
        with self._connection() as db:
            return [self._stored_event(row).callback_query_id for row in db.execute(
                "SELECT * FROM inbox WHERE kind='callback' AND callback_ack_state='pending' "
                "ORDER BY update_id")]

    def mark_callback_ack(self, query_id: str, *, expired: bool = False) -> None:
        if type(query_id) is not str or not query_id or type(expired) is not bool:
            raise ValueError('Invalid callback acknowledgement')
        with self._connection(write=True) as db:
            db.execute("UPDATE inbox SET callback_ack_state=? WHERE callback_query_id=? "
                       "AND kind='callback' AND callback_ack_state='pending'",
                       ('expired' if expired else 'sent', query_id))

    @staticmethod
    def _delivery_notice(db, notice_id, chat_id, message_id, digest):
        if (type(notice_id) is not str or not notice_id or type(chat_id) is not int
                or chat_id <= 0 or type(message_id) is not int or message_id <= 0
                or type(digest) is not str or not digest):
            raise ValueError('Invalid delivery receipt')
        notice = db.execute('SELECT * FROM outbox WHERE id=?', (notice_id,)).fetchone()
        if notice is None or notice['chat_id'] != chat_id:
            raise ValueError('Delivery notice missing or owner mismatch')
        Reply.model_validate_json(notice['reply_json'])
        if notice['update_id'] is not None:
            source = db.execute('SELECT * FROM inbox WHERE update_id=?',
                                (notice['update_id'],)).fetchone()
            if (source is None or (source['user_id'], source['chat_id']) != (chat_id, chat_id)
                    or not source['completed'] or source['reply_json'] != notice['reply_json']):
                raise ValueError('Delivery source mismatch')
            Repository._stored_event(source)
        return notice

    def record_delivery(self, notice_id: str, chat_id: int, message_id: int, digest: str) -> None:
        with self._connection(write=True) as db:
            self._delivery_notice(db, notice_id, chat_id, message_id, digest)
            existing = db.execute('SELECT digest FROM telegram_deliveries WHERE '
                                  'notice_id=? AND chat_id=? AND message_id=?',
                                  (notice_id, chat_id, message_id)).fetchone()
            if existing is not None:
                if existing['digest'] != digest:
                    raise ValueError('Conflicting delivery digest')
                self._guided_delivery(db, notice_id, chat_id, message_id, digest)
                return
            db.execute('INSERT INTO telegram_deliveries VALUES (?,?,?,?)',
                       (notice_id, chat_id, message_id, digest))
            self._guided_delivery(db, notice_id, chat_id, message_id, digest)

    def known_delivery(self, notice_id: str, chat_id: int, message_id: int, digest: str) -> bool:
        with self._connection() as db:
            try:
                self._delivery_notice(db, notice_id, chat_id, message_id, digest)
            except (ValueError, TypeError):
                return False
            return db.execute('SELECT 1 FROM telegram_deliveries WHERE '
                              'notice_id=? AND chat_id=? AND message_id=? AND digest=?',
                              (notice_id, chat_id, message_id, digest)).fetchone() is not None

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
        event, reply = self.event_result(update_id)
        if isinstance(event, IncomingCallback):
            raise TypeError('A callback is not a legacy message')
        return event, reply

    def event_result(self, update_id: int) -> tuple[IncomingEvent, Reply | None]:
        with self._connection() as db:
            row = db.execute("SELECT * FROM inbox WHERE update_id=?", (update_id,)).fetchone()
            if row is None:
                raise KeyError(update_id)
            return (
                self._stored_event(row),
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
            self._agent_message(source)
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
