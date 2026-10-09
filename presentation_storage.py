"""Immutable reply jobs; preparation and finalization own separate short transactions."""

from datetime import datetime
from uuid import uuid4

from domain import IncomingMessage, Intent, Reply
from presentation import PreparedPresentation, PresentationSnapshot
from presentation_replies import build_presentation


class PresentationRepository:
    def _read_prepared(self, db, update_id: int) -> PreparedPresentation | None:
        row = db.execute("SELECT * FROM presentation_jobs WHERE update_id=?", (update_id,)).fetchone()
        if row is None:
            return None
        source = db.execute("SELECT * FROM inbox WHERE update_id=?", (update_id,)).fetchone()
        if (source is None or (row["user_id"], row["chat_id"]) !=
                (source["user_id"], source["chat_id"])):
            raise ValueError("Presentation source identity mismatch or orphan job")
        if 'kind' in tuple(source.keys()) and source['kind'] != 'message':
            raise ValueError('A callback cannot have a generative presentation job')
        IncomingMessage(**{k: source[k] for k in ("update_id", "user_id", "chat_id", "text")})
        snapshot = PresentationSnapshot.model_validate_json(row["snapshot_json"])
        if (source["text"].strip().startswith("/") or snapshot.fallback.order_id is not None
                or db.execute("SELECT 1 FROM orders WHERE source_update_id=?", (update_id,)).fetchone()):
            raise ValueError("Presentation source conflicts with deterministic work")
        if not source["completed"] and (source["reply_json"] is not None or db.execute(
                "SELECT 1 FROM outbox WHERE update_id=?", (update_id,)).fetchone()):
            raise ValueError("Pending presentation conflicts with completed work")
        if source["completed"]:
            reply = Reply.model_validate_json(source["reply_json"])
            if reply.order_id is not None:
                raise ValueError("Finalized presentation cannot authorize an order")
            notices = db.execute("SELECT chat_id,reply_json FROM outbox WHERE update_id=?",
                                 (update_id,)).fetchall()
            if (len(notices) != 1 or notices[0]["chat_id"] != source["chat_id"]
                    or Reply.model_validate_json(notices[0]["reply_json"]) != reply):
                raise ValueError("Finalized presentation conflicts with its durable notice")
        prepared = PreparedPresentation(update_id=row["update_id"], user_id=row["user_id"],
                                        chat_id=row["chat_id"], snapshot=snapshot)
        return PreparedPresentation.model_validate_json(prepared.model_dump_json())

    def prepared_presentation(self, update_id: int) -> PreparedPresentation | None:
        with self._connection() as db:
            return self._read_prepared(db, update_id)

    @staticmethod
    def _complete_reply(db, source, reply: Reply) -> Reply:
        reply = Reply.model_validate_json(reply.model_dump_json())
        payload = reply.model_dump_json()
        db.execute("UPDATE inbox SET completed=1,reply_json=? WHERE update_id=?",
                   (payload, source["update_id"]))
        db.execute("INSERT INTO outbox(id,update_id,chat_id,reply_json) VALUES (?,?,?,?)",
                   (str(uuid4()), source["update_id"], source["chat_id"], payload))
        return reply

    def prepare_dialogue(
        self, update_id: int, proposal: Intent | None, mode: str, *, now: datetime,
    ) -> PreparedPresentation | Reply:
        if mode not in ("dry_run", "live"):
            raise ValueError("Invalid mode")
        with self._connection(write=True) as db:
            prepared = self._read_prepared(db, update_id)
            source = db.execute("SELECT * FROM inbox WHERE update_id=?", (update_id,)).fetchone()
            if source is None:
                raise KeyError(update_id)
            if 'kind' in tuple(source.keys()) and source['kind'] != 'message':
                raise ValueError('A callback cannot enter legacy presentation')
            if source["completed"]:
                return Reply.model_validate_json(source["reply_json"])
            if prepared is not None:
                return prepared
            decision, affected, original, lines, legacy, observations, reply = self._apply_dialogue(
                db, source, proposal, mode, now=now)
            # Commands and operational legacy replies never acquire generative jobs.
            if (source["text"].strip().startswith("/") or reply.order_id is not None
                    or (decision.legacy_intent and decision.legacy_intent.action not in
                        {"list", "product_query"})):
                return self._complete_reply(db, source, reply)
            snapshot = build_presentation(decision, affected, lines, legacy,
                                          observations=observations, original=original)
            if snapshot.fallback.order_id is not None:
                raise ValueError("Presentation fallback cannot authorize an order")
            db.execute("INSERT INTO presentation_jobs VALUES (?,?,?,?,?)",
                       (update_id, source["user_id"], source["chat_id"],
                        snapshot.model_dump_json(), now.isoformat()))
            return self._read_prepared(db, update_id)

    def finalize_presentation(self, update_id: int, reply: Reply) -> Reply:
        with self._connection(write=True) as db:
            prepared = self._read_prepared(db, update_id)
            if prepared is None:
                raise ValueError("No prepared presentation")
            source = db.execute("SELECT * FROM inbox WHERE update_id=?", (update_id,)).fetchone()
            if source["completed"]:
                return Reply.model_validate_json(source["reply_json"])
            reply = Reply.model_validate_json(reply.model_dump_json())
            if reply.order_id is not None:
                raise ValueError("Presentation cannot authorize an order")
            return self._complete_reply(db, source, reply)
