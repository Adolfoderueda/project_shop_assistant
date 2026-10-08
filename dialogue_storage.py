"""Expiring dialogue memory, using the repository's caller-owned transactions."""

import sqlite3
from datetime import datetime
from uuid import uuid4

from catalog import resolve_product
from dialogue import DIALOGUE_TTL, DialogueMutation, DialogueState, LineRef, canonical_name, expired
from dialogue_controller import reduce_dialogue
from dialogue_replies import render_dialogue_result
from dialogue_requests import classify_request
from domain import IncomingMessage, Intent, Reply


class DialogueRepository:
    def apply_dialogue(self, update_id: int, proposal: Intent | None, mode: str, *, now: datetime) -> Reply:
        if mode not in ("dry_run", "live"):
            raise ValueError("Invalid mode")
        with self._connection(write=True) as db:
            prepared = self._read_prepared(db, update_id)
            source = db.execute("SELECT * FROM inbox WHERE update_id=?", (update_id,)).fetchone()
            if source is None:
                raise KeyError(update_id)
            if source["completed"]:
                return Reply.model_validate_json(source["reply_json"])
            if prepared is not None:
                return self._complete_reply(db, source, prepared.snapshot.fallback)
            *_, reply = self._apply_dialogue(db, source, proposal, mode, now=now)
            return self._complete_reply(db, source, reply)

    def _apply_dialogue(self, db, source, proposal, mode, *, now):
        """Apply once in the caller transaction and return typed presentation witnesses."""
        update_id = source["update_id"]
        if proposal is not None:
            proposal = Intent.model_validate_json(proposal.model_dump_json())
        message = IncomingMessage(**{k: source[k] for k in ("update_id", "user_id", "chat_id", "text")})
        state = self._read_dialogue_state(db, message.user_id, message.chat_id)
        request = classify_request(message.text)
        if request is not None and request.action == "greet":
            # Keep validated inbox/state provenance and normal prepare/finalize,
            # but neither inspect private rows/reservations nor rewrite context.
            decision = reduce_dialogue(message, proposal, state, [], frozenset(), now=now)
            reply = render_dialogue_result(decision, None, [], None)
            return decision, None, None, [], None, [], reply
        before = self._lines(db)
        decision = reduce_dialogue(message, proposal, state, before, frozenset(
            r[0] for r in db.execute("SELECT line_id FROM reservations")
        ), now=now)
        affected = None
        legacy_reply = None
        observations = []
        mutation = decision.mutation
        if mutation is not None:
            mutation = DialogueMutation.model_validate_json(mutation.model_dump_json())
        original = next((l for l in before if mutation and mutation.target
                         and l.id == mutation.target.id), None)
        if mutation:
            if mutation.kind == "add":
                if mutation.quantity is None:
                    raise ValueError("Dialogue additions require a quantity")
                line_id = str(uuid4())
                db.execute("INSERT INTO list_lines VALUES (?,?,?,?,1,?)", (
                    line_id, resolve_product(mutation.description), mutation.description,
                    mutation.quantity, update_id,
                ))
            elif mutation.kind == "set_quantity":
                line_id = mutation.target.id
                db.execute("UPDATE list_lines SET quantity=?,revision=revision+1 WHERE id=? AND revision=?",
                           (mutation.quantity, line_id, mutation.target.revision))
            elif mutation.kind == "replace":
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
            elif mutation.kind == "increment":
                final = (DialogueState.model_validate_json(decision.state.model_dump_json())
                         if decision.state else None)
                target = mutation.target
                if (target is None or final is None or final.focus is None
                        or state is None or state.question != "confirm_increment" or expired(state, now)
                        or state.pending_kind != "increment" or state.target != target
                        or state.base_quantity != mutation.expected_base
                        or state.additional_quantity != mutation.additional_quantity
                        or state.proposal_quantity != mutation.quantity
                        or final.pending_kind != "increment" or not final.increment_confirmed
                        or final.question is not None or final.target != target
                        or final.focus.line != target or final.focus.description != mutation.description
                        or final.base_quantity != mutation.expected_base
                        or final.additional_quantity != mutation.additional_quantity
                        or final.proposal_quantity != mutation.quantity
                        or mutation.expected_base + mutation.additional_quantity != mutation.quantity):
                    raise ValueError("Increment requires confirmed origin, base, delta and total")
                current = next((l for l in self._lines(db) if l.id == target.id), None)
                if (current is None or current.revision != target.revision
                        or current.quantity is None or current.quantity != mutation.expected_base
                        or canonical_name(current.description) != canonical_name(mutation.description)
                        or db.execute("SELECT 1 FROM reservations WHERE line_id=?", (target.id,)).fetchone()):
                    raise ValueError("Increment origin changed or is reserved")
                line_id = target.id
                changed = db.execute(
                    "UPDATE list_lines SET quantity=?,revision=revision+1 "
                    "WHERE id=? AND revision=? AND quantity=? AND NOT EXISTS "
                    "(SELECT 1 FROM reservations WHERE line_id=?)",
                    (mutation.quantity, line_id, target.revision, mutation.expected_base, line_id),
                )
                if changed.rowcount != 1:
                    raise ValueError("Increment must update exactly one current, unreserved line")
            affected = next(l for l in self._lines(db) if l.id == line_id)
            reference = LineRef(id=affected.id, revision=affected.revision)
            rebound = decision.state.model_copy(update={
                "focus": decision.state.focus.model_copy(update={"line": reference}),
                "target": reference if decision.state.question == "quantity" else None,
                "pending_kind": None,
            })
            if mutation.kind in {"replace", "add", "increment"}:
                rebound = rebound.model_copy(update={
                    "candidates": (), "proposal_quantity": None,
                    "replacement_confirmed": False, "duplicate_confirmed": False,
                    "base_quantity": None, "additional_quantity": None,
                    "increment_confirmed": False, "question": None, "options": (),
                })
            decision = decision.model_copy(update={"state": rebound})
        elif decision.legacy_intent:
            legacy_reply = self._apply(db, update_id, decision.legacy_intent, mode)
            intent = decision.legacy_intent
            if intent.action == "product_query" and len(intent.lines) == 1 and intent.lines[0].description:
                observations = self._find_products(db, intent.lines[0].description)
        self._write_dialogue_state(db, decision.state, message.user_id, message.chat_id)
        from interpreter import purchase_authorized
        read_only = decision.legacy_intent is not None and decision.legacy_intent.action in {'list', 'product_query'}
        agent_schema = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                  "AND name='conversation_routes'").fetchone() is not None
        if not agent_schema:
            # Pre-agent databases may still be preparing legacy work before
            # their migration creates these tables.
            pass
        elif not read_only and (message.text.strip().startswith('/') or purchase_authorized(message.text)):
            # A new explicit command replaces any old continuation/agent permission.
            self._write_agent_proposal(db, source, None)
            db.execute('UPDATE conversation_routes SET command_update_id=NULL WHERE user_id=? AND chat_id=?',
                       (message.user_id, message.chat_id))
            if self._command_context_reply(db, message, decision.state) is not None:
                self._record_command_origin(db, source)
        elif decision.state is None or decision.state.question is None:
            # Read-only operations preserve live continuations/TTL, not links to
            # continuations the reducer discarded (expired, stale or finished).
            db.execute('UPDATE conversation_routes SET command_update_id=NULL WHERE user_id=? AND chat_id=?',
                       (message.user_id, message.chat_id))
        elif decision.state.focus is not None:
            db.execute('UPDATE conversation_routes SET command_update_id=NULL '
                       'WHERE user_id=? AND chat_id=? AND command_update_id<>?',
                       (message.user_id, message.chat_id, decision.state.focus.source_update_id))
        lines = self._lines(db)
        reply = render_dialogue_result(decision, affected, lines, legacy_reply)
        return decision, affected, original, lines, legacy_reply, observations, reply

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
