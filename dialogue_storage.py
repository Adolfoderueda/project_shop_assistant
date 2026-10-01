"""Expiring dialogue memory, using the repository's caller-owned transactions."""

import sqlite3
from datetime import datetime

from dialogue import DIALOGUE_TTL, DialogueState, expired


class DialogueRepository:
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
