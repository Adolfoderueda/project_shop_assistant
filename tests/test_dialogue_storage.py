import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from dialogue import DIALOGUE_TTL, DialogueState, ProductMention
from domain import IncomingMessage, Intent, IntentLine
from storage import OBSERVED_PRODUCTS, Repository
from tests.dialogue_support import make_repo, seed_line


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


@pytest.fixture
def state(repo):
    repo.ingest_batch([IncomingMessage(update_id=1, user_id=7, chat_id=7, text="arroz")], 2)
    now = datetime(2026, 10, 1, tzinfo=UTC)
    return DialogueState(
        user_id=7, chat_id=7, focus=ProductMention(description="arroz", source_update_id=1),
        question="quantity", updated_at=now, expires_at=now + DIALOGUE_TTL,
    )


def v5_repo(tmp_path):
    repo = Repository(tmp_path / "v5.db")
    with sqlite3.connect(repo.path) as db:
        for number in range(1, 6):
            db.executescript((Path(__file__).parents[1] / f"migrations/{number:03}.sql").read_text())
        db.executemany("INSERT INTO observed_products VALUES (?,?,?,?,?,?,?,?,?)", OBSERVED_PRODUCTS)
    return repo


def snapshots(repo):
    with sqlite3.connect(repo.path) as db:
        return {table: db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                for table in ("list_lines", "orders", "order_lines", "execution", "reservations",
                              "inbox", "outbox", "meta", "observed_products")}


def test_v5_upgrade_preserves_list_orders_offset_and_observations(tmp_path):
    repo = v5_repo(tmp_path)
    seed_line(repo, "arroz", 2)
    repo.ingest_batch([IncomingMessage(update_id=2, user_id=7, chat_id=7, text="comprar")], 42)
    reply = repo.apply_intent(2, Intent(action="buy"), "dry_run")
    before = snapshots(repo)
    order = repo.get_order(reply.order_id)
    repo.migrate()
    repo.migrate()
    assert snapshots(repo) == before
    assert repo.get_order(reply.order_id) == order
    assert repo.telegram_offset() == 42
    with sqlite3.connect(repo.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 9
        assert db.execute("SELECT count(*) FROM observed_products").fetchone()[0] == 4


def test_legacy_undated_clarifications_do_not_grant_fresh_permissions(tmp_path):
    repo = v5_repo(tmp_path)
    line = seed_line(repo, "arroz")
    before = repo.list_lines()
    with sqlite3.connect(repo.path) as db:
        for user_id, action in ((7, "set_quantity"), (8, "remove")):
            intent = Intent(action=action, lines=[IntentLine(line_id=line.id)])
            db.execute("INSERT INTO clarifications VALUES (?,?)", (user_id, intent.model_dump_json()))
    repo.migrate()
    assert repo.list_lines() == before
    assert repo.pending_clarification(7) is None
    assert repo.pending_clarification(8) is None
    assert repo.dialogue_state(7, 7, now=datetime(2026, 10, 1, tzinfo=UTC)) is None
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM clarifications").fetchone()[0] == 0


def test_state_roundtrip_owner_and_read_does_not_renew(repo, state):
    with repo._connection(write=True) as db:
        repo._write_dialogue_state(db, state, 7, 7)
    reopened = Repository(repo.path)
    reopened.migrate()
    assert reopened.dialogue_state(7, 7, now=state.updated_at + timedelta(seconds=899)) == state
    for user_id, chat_id in ((8, 8), (7, 8), (8, 7)):
        assert reopened.dialogue_state(user_id, chat_id, now=state.updated_at) is None
    assert reopened.dialogue_state(7, 7, now=state.updated_at + timedelta(seconds=900)) is None
    with reopened._connection() as db:
        assert reopened._read_dialogue_state(db, 7, 7) == state
    reopened.assert_authorized_owner(7)


def test_foreign_state_blocks_owner_assertion(repo, state):
    with repo._connection(write=True) as db:
        db.execute("INSERT INTO dialogue_state VALUES (?,?,?)", (8, 8, state.model_dump_json()))
    with pytest.raises(PermissionError, match="another owner"):
        repo.assert_authorized_owner(7)


@pytest.mark.parametrize("change", [
    {"user_id": 8}, {"chat_id": 8}, {"user_id": "7"}, {"extra": True},
    {"updated_at": "2026-10-01T00:00:00"},
    {"expires_at": "2026-10-01T00:00:00Z"},
    {"expires_at": "2026-10-01T01:00:00Z"},
    {"focus": {"description": "arroz", "source_update_id": 999}},
])
def test_corrupt_state_fails_closed(repo, state, change):
    payload = json.loads(state.model_dump_json()) | change
    with repo._connection(write=True) as db:
        db.execute("INSERT INTO dialogue_state VALUES (7,7,?)", (json.dumps(payload),))
    assert repo.dialogue_state(7, 7, now=state.updated_at) is None


def test_invalid_json_fails_closed(repo, state):
    with repo._connection(write=True) as db:
        db.execute("INSERT INTO dialogue_state VALUES (7,7,'not json')")
    assert repo.dialogue_state(7, 7, now=state.updated_at) is None


@pytest.mark.parametrize("user_id,chat_id", [(8, 7), (7, 8)])
def test_focus_source_must_belong_to_same_owner_on_read_and_write(repo, state, user_id, chat_id):
    repo.ingest_batch([IncomingMessage(update_id=2, user_id=user_id, chat_id=chat_id, text="arroz")], 3)
    invalid = state.model_copy(update={"focus": ProductMention(description="arroz", source_update_id=2)})
    with repo._connection(write=True) as db:
        with pytest.raises(ValueError):
            repo._write_dialogue_state(db, invalid, 7, 7)
        db.execute("INSERT INTO dialogue_state VALUES (7,7,?)", (invalid.model_dump_json(),))
    assert repo.dialogue_state(7, 7, now=state.updated_at) is None


def test_write_rejects_key_mismatch_and_invalid_dates(repo, state):
    with repo._connection(write=True) as db:
        for invalid in (state.model_copy(update={"user_id": 8}),
                        state.model_copy(update={"expires_at": state.updated_at})):
            with pytest.raises(ValueError):
                repo._write_dialogue_state(db, invalid, 7, 7)
        assert repo._read_dialogue_state(db, 7, 7) is None


def test_write_clear_and_rollback_use_callers_transaction(repo, state):
    with pytest.raises(RuntimeError), repo._connection(write=True) as db:
        repo._write_dialogue_state(db, state, 7, 7)
        raise RuntimeError("injected")
    assert repo.dialogue_state(7, 7, now=state.updated_at) is None
    with repo._connection(write=True) as db:
        repo._write_dialogue_state(db, state, 7, 7)
        repo._write_dialogue_state(db, None, 8, 8)
        assert repo._read_dialogue_state(db, 7, 7) == state
        repo._write_dialogue_state(db, None, 7, 7)
    assert repo.dialogue_state(7, 7, now=state.updated_at) is None


def test_future_schema_is_rejected(repo):
    with sqlite3.connect(repo.path) as db:
        db.execute("PRAGMA user_version=10")
    with pytest.raises(ValueError, match="newer"):
        repo.migrate()
