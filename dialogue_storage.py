"""Expiring dialogue memory, using the repository's caller-owned transactions."""

import sqlite3
from datetime import datetime
from uuid import uuid4

from catalog import resolve_product
from dialogue import DIALOGUE_TTL, DialogueState, LineRef, canonical_name, expired
from dialogue_controller import reduce_dialogue
from dialogue_replies import render_dialogue_result
from domain import IncomingMessage, Intent, Reply


class DialogueRepository:
    def apply_dialogue(self, update_id: int, proposal: Intent | None, mode: str, *, now: datetime) -> Reply:
        if mode not in ("dry_run", "live"):
            raise ValueError("Invalid mode")
        with self._connection(write=True) as db:
            source = db.execute("SELECT * FROM inbox WHERE update_id=?", (update_id,)).fetchone()
            if source is None:
                raise KeyError(update_id)
            if source["completed"]:
                return Reply.model_validate_json(source["reply_json"])
            if proposal is not None:
                proposal = Intent.model_validate_json(proposal.model_dump_json())
            message = IncomingMessage(**{k: source[k] for k in ("update_id", "user_id", "chat_id", "text")})
            state = self._read_dialogue_state(db, message.user_id, message.chat_id)
            decision = reduce_dialogue(message, proposal, state, self._lines(db), frozenset(
                r[0] for r in db.execute("SELECT line_id FROM reservations")
            ), now=now)
            affected = None
            legacy_reply = None
            mutation = decision.mutation
            if mutation:
                if mutation.kind == "add":
                    line_id = str(uuid4())
                    db.execute("INSERT INTO list_lines VALUES (?,?,?,?,1,?)", (
                        line_id, resolve_product(mutation.description), mutation.description,
                        mutation.quantity, update_id,
                    ))
                elif mutation.kind == "set_quantity":
                    line_id = mutation.target.id
                    db.execute("UPDATE list_lines SET quantity=?,revision=revision+1 WHERE id=? AND revision=?",
                               (mutation.quantity, line_id, mutation.target.revision))
                else:
                    final = decision.state
                    target = mutation.target
                    if (target is None or final is None or final.focus is None
                            or not final.replacement_confirmed or final.target != target
                            or final.question is not None or mutation.quantity is None
                            or final.proposal_quantity != mutation.quantity
                            or final.focus.description != mutation.description):
                        raise ValueError("Replacement requires confirmed origin, destination and quantity")
                    current = next((l for l in self._lines(db) if l.id == target.id), None)
                    if (current is None or current.revision != target.revision
                            or db.execute("SELECT 1 FROM reservations WHERE line_id=?", (target.id,)).fetchone()):
                        raise ValueError("Replacement origin changed or is reserved")
                    conflicts = tuple(LineRef(id=l.id, revision=l.revision) for l in self._lines(db)
                                      if l.id != target.id and canonical_name(l.description)
                                      == canonical_name(mutation.description))
                    if conflicts != final.candidates or (conflicts and not final.duplicate_confirmed):
                        raise ValueError("Replacement duplicate conflict requires explicit confirmation")
                    line_id = target.id
                    changed = db.execute(
                        "UPDATE list_lines SET description=?,product_id=?,quantity=?,revision=revision+1 "
                        "WHERE id=? AND revision=? AND NOT EXISTS "
                        "(SELECT 1 FROM reservations WHERE line_id=?)",
                        (mutation.description, resolve_product(mutation.description), mutation.quantity,
                         line_id, target.revision, line_id),
                    )
                    if changed.rowcount != 1:
                        raise ValueError("Replacement must update exactly one current, unreserved line")
                affected = next(l for l in self._lines(db) if l.id == line_id)
                reference = LineRef(id=affected.id, revision=affected.revision)
                rebound = decision.state.model_copy(update={
                    "focus": decision.state.focus.model_copy(update={"line": reference}),
                    "target": reference if decision.state.question == "quantity" else None,
                })
                if mutation.kind == "replace":
                    rebound = rebound.model_copy(update={
                        "candidates": (), "proposal_quantity": None,
                        "replacement_confirmed": False, "duplicate_confirmed": False,
                    })
                decision = decision.model_copy(update={"state": rebound})
            elif decision.legacy_intent:
                legacy_reply = self._apply(db, update_id, decision.legacy_intent, mode)
            self._write_dialogue_state(db, decision.state, message.user_id, message.chat_id)
            reply = render_dialogue_result(decision, affected, self._lines(db), legacy_reply)
            payload = reply.model_dump_json()
            db.execute("UPDATE inbox SET completed=1,reply_json=? WHERE update_id=?", (payload, update_id))
            db.execute("INSERT INTO outbox(id,update_id,chat_id,reply_json) VALUES (?,?,?,?)",
                       (str(uuid4()), update_id, message.chat_id, payload))
            return reply

    def dialogue_state(
        self, user_id: int, chat_id: int, *, now: datetime,
    ) -> DialogueState | None:
        with self._connection() as db:
            state = self._read_dialogue_state(db, user_id, chat_id)
            return state if state is not None and not expired(state, now) else None

    @staticmethod
    def _validate_dialogue_state(
        db: sqlite3.Connection, state: DialogueState, user_id: int, chat_id: int,
    ) -> None:
        if (state.user_id, state.chat_id) != (user_id, chat_id):
            raise ValueError("Dialogue state identity does not match its key")
        if state.expires_at - state.updated_at != DIALOGUE_TTL:
            raise ValueError("Dialogue state must expire after 15 minutes")
        if state.focus is not None:
            source = db.execute(
                "SELECT 1 FROM inbox WHERE update_id=? AND user_id=? AND chat_id=?",
                (state.focus.source_update_id, user_id, chat_id),
            ).fetchone()
            if source is None:
                raise ValueError("Dialogue focus source does not belong to this user/chat")

    def _read_dialogue_state(
        self, db: sqlite3.Connection, user_id: int, chat_id: int,
    ) -> DialogueState | None:
        row = db.execute(
            "SELECT state_json FROM dialogue_state WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        ).fetchone()
        if row is None:
            return None
        try:
            state = DialogueState.model_validate_json(row[0])
            self._validate_dialogue_state(db, state, user_id, chat_id)
        except ValueError:
            # Corruption must not yield partially valid permissions or renew memory.
            return None
        return state

    def _write_dialogue_state(
        self, db: sqlite3.Connection, state: DialogueState | None, user_id: int, chat_id: int,
    ) -> None:
        if state is None:
            db.execute("DELETE FROM dialogue_state WHERE user_id=? AND chat_id=?", (user_id, chat_id))
            return
        # Revalidate even model_copy-produced instances before persisting permissions.
        payload = state.model_dump_json()
        validated = DialogueState.model_validate_json(payload)
        self._validate_dialogue_state(db, validated, user_id, chat_id)
        db.execute(
            "INSERT INTO dialogue_state(user_id,chat_id,state_json) VALUES (?,?,?) "
            "ON CONFLICT(user_id,chat_id) DO UPDATE SET state_json=excluded.state_json",
            (user_id, chat_id, payload),
        )
