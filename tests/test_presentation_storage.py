import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from domain import IncomingMessage, Intent, IntentLine, Reply
from presentation import PreparedPresentation
from storage import OBSERVED_PRODUCTS, Repository
from tests.dialogue_support import make_repo, seed_line

NOW = datetime(2026, 10, 8, tzinfo=UTC)


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


def ingest(repo, text, number=10):
    repo.ingest_batch([IncomingMessage(update_id=number, user_id=7, chat_id=7, text=text)], number + 1)


def prepare_add(repo):
    ingest(repo, "necesito arroz")
    first = repo.prepare_dialogue(10, Intent(action="add", lines=[IntentLine(description="arroz")]),
                                 "dry_run", now=NOW)
    repo.finalize_presentation(10, first.snapshot.fallback)
    ingest(repo, "2", 11)
    return repo.prepare_dialogue(11, None, "dry_run", now=NOW + timedelta(seconds=1))


def durable(repo):
    with sqlite3.connect(repo.path) as db:
        tables = ("list_lines", "orders", "order_lines", "execution", "reservations", "inbox",
                  "outbox", "meta", "observed_products", "dialogue_state")
        return {t: db.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall() for t in tables}


def test_v6_upgrade_preserves_all_durable_work(tmp_path):
    repo = Repository(tmp_path / "v6.db")
    with sqlite3.connect(repo.path) as db:
        for n in range(1, 7):
            db.executescript((Path(__file__).parents[1] / f"migrations/{n:03}.sql").read_text())
        db.executemany("INSERT INTO observed_products VALUES (?,?,?,?,?,?,?,?,?)", OBSERVED_PRODUCTS)
    line = seed_line(repo, "arroz", 2)
    ingest(repo, "necesito avena", 2)
    with repo._connection(write=True) as db:
        source = db.execute("SELECT * FROM inbox WHERE update_id=2").fetchone()
        *_, reply = repo._apply_dialogue(db, source, Intent(action="add", lines=[
            IntentLine(description="avena")]), "dry_run", now=NOW)
        repo._complete_reply(db, source, reply)
    ingest(repo, "/comprar", 3)
    order = repo.apply_intent(3, Intent(action="buy", lines=[IntentLine(line_id=line.id)]), "dry_run")
    assert order.order_id is not None
    before = durable(repo)
    assert all(before[t] for t in before)
    repo.migrate()
    repo.migrate()
    assert durable(repo) == before
    with sqlite3.connect(repo.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 7
        db.execute("PRAGMA user_version=8")
    with pytest.raises(ValueError, match="newer"):
        repo.migrate()


def test_prepare_commits_once_without_sendable_notice(repo):
    job = prepare_add(repo)
    assert isinstance(job, PreparedPresentation)
    assert job.snapshot.kind == "updated"
    assert repo.list_lines()[0].quantity == 2
    assert repo.message_result(11)[1] is None
    assert len(repo.pending_notices()) == 1  # Only the previous question was finalized.
    assert Repository(repo.path).prepared_presentation(11) == job
    assert repo.dialogue_state(7, 7, now=NOW).focus.line.revision == 2


def test_prepare_replay_ignores_new_proposal(repo):
    job = prepare_add(repo)
    before = durable(repo)
    assert repo.prepare_dialogue(11, Intent(action="buy"), "dry_run", now=NOW + timedelta(days=1)) == job
    assert durable(repo) == before


def test_finalize_is_atomic_and_idempotent(repo):
    job = prepare_add(repo)
    reply = Reply(text="Respuesta validada")
    assert repo.finalize_presentation(11, reply) == reply
    assert repo.finalize_presentation(11, Reply(text="otra")) == reply
    assert repo.prepare_dialogue(11, None, "dry_run", now=NOW) == reply
    assert repo.prepared_presentation(11) == job
    assert repo.message_result(11)[1] == reply
    with repo._connection() as db:
        assert db.execute("SELECT count(*) FROM outbox WHERE update_id=11").fetchone()[0] == 1


def test_snapshot_uses_transaction_rows_not_old_context(repo):
    line = seed_line(repo, "arroz", 2)
    with repo._connection(write=True) as db:
        db.execute("UPDATE list_lines SET quantity=8 WHERE id=?", (line.id,))
        db.execute("UPDATE observed_products SET price_cents=1234 WHERE product_id='diapers'")
    ingest(repo, "dame mi lista")
    job = repo.prepare_dialogue(10, Intent(action="list"), "dry_run", now=NOW)
    assert "8 envases" in job.snapshot.facts[0].text
    ingest(repo, "qué sabes de Dodot talla 3", 11)
    job = repo.prepare_dialogue(11, Intent(action="product_query", lines=[
        IntentLine(description="Dodot talla 3")]), "dry_run", now=NOW)
    assert job.snapshot.kind == "product"
    assert all("12,34 €" in f.text for f in job.snapshot.facts)


@pytest.mark.parametrize("damage", ["foreign", "chat", "source", "orphan", "json", "version",
                                   "extra", "order", "notice", "reply", "command", "order_source"])
def test_orphan_foreign_corrupt_and_conflicting_job_fail_closed(repo, damage):
    job = prepare_add(repo)
    with sqlite3.connect(repo.path) as db:
        if damage == "foreign":
            db.execute("UPDATE presentation_jobs SET user_id=8 WHERE update_id=11")
        elif damage == "chat":
            db.execute("UPDATE presentation_jobs SET chat_id=8 WHERE update_id=11")
        elif damage == "source":
            db.execute("UPDATE inbox SET user_id=8 WHERE update_id=11")
        elif damage == "orphan":
            db.execute("DELETE FROM inbox WHERE update_id=11")
        elif damage == "notice":
            db.execute("INSERT INTO outbox(id,update_id,chat_id,reply_json) VALUES ('bad',11,7,?)",
                       (Reply(text="bad").model_dump_json(),))
        elif damage == "command":
            db.execute("UPDATE inbox SET text='/lista' WHERE update_id=11")
        elif damage == "reply":
            db.execute("UPDATE inbox SET reply_json=? WHERE update_id=11",
                       (Reply(text="conflict").model_dump_json(),))
        elif damage == "order_source":
            db.execute("INSERT INTO orders(id,mode,source_update_id) VALUES ('conflict','dry_run',11)")
        else:
            payload = json.loads(job.snapshot.model_dump_json())
            if damage == "version":
                payload["version"] = 2
            elif damage == "extra":
                payload["authority"] = True
            elif damage == "order":
                payload["fallback"]["order_id"] = "bad"
            db.execute("UPDATE presentation_jobs SET snapshot_json=? WHERE update_id=11",
                       ("not json" if damage == "json" else json.dumps(payload),))
    before = repo.list_lines()
    for operation in (lambda: repo.prepared_presentation(11),
                      lambda: repo.prepare_dialogue(11, None, "dry_run", now=NOW),
                      lambda: repo.finalize_presentation(11, Reply(text="bad")),
                      lambda: repo.assert_authorized_owner(7)):
        with pytest.raises((ValueError, PermissionError)):
            operation()
    assert repo.list_lines() == before


def test_rollback_prepare_and_finalize(repo):
    ingest(repo, "necesito arroz")
    with repo._connection(write=True) as db:
        db.execute("CREATE TRIGGER fail_prepare BEFORE INSERT ON presentation_jobs "
                   "BEGIN SELECT RAISE(ABORT,'injected'); END")
    before = durable(repo)
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        repo.prepare_dialogue(10, Intent(action="add", lines=[IntentLine(description="arroz")]),
                              "dry_run", now=NOW)
    assert durable(repo) == before
    with repo._connection(write=True) as db:
        db.execute("DROP TRIGGER fail_prepare")
    job = repo.prepare_dialogue(10, Intent(action="add", lines=[IntentLine(description="arroz")]),
                                "dry_run", now=NOW)
    with repo._connection(write=True) as db:
        db.execute("CREATE TRIGGER fail_finalize BEFORE INSERT ON outbox "
                   "BEGIN SELECT RAISE(ABORT,'injected'); END")
    before = durable(repo)
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        repo.finalize_presentation(10, job.snapshot.fallback)
    assert durable(repo) == before
    assert repo.prepared_presentation(10) == job


def test_commands_and_existing_routes_stay_deterministic(repo):
    ingest(repo, "/lista", 5)
    assert repo.prepare_dialogue(5, None, "dry_run", now=NOW) == Reply(text="La lista está vacía.")
    assert repo.prepared_presentation(5) is None
    job = prepare_add(repo)
    assert repo.apply_dialogue(11, Intent(action="buy"), "dry_run", now=NOW) == job.snapshot.fallback
    assert len(repo.list_lines()) == 1


def test_finalize_rejects_order_and_unprepared_work(repo):
    job = prepare_add(repo)
    with pytest.raises(ValueError):
        repo.finalize_presentation(11, Reply(text="bad", order_id="bad"))
    ingest(repo, "hola", 12)
    with pytest.raises(ValueError):
        repo.finalize_presentation(12, job.snapshot.fallback)


@pytest.mark.parametrize("damage", ["missing", "foreign", "payload"])
def test_finalized_job_requires_matching_durable_notice(repo, damage):
    job = prepare_add(repo)
    repo.finalize_presentation(11, job.snapshot.fallback)
    with repo._connection(write=True) as db:
        if damage == "missing":
            db.execute("DELETE FROM outbox WHERE update_id=11")
        elif damage == "foreign":
            db.execute("UPDATE outbox SET chat_id=8 WHERE update_id=11")
        else:
            db.execute("UPDATE outbox SET reply_json=? WHERE update_id=11",
                       (Reply(text="different").model_dump_json(),))
    with pytest.raises(ValueError):
        repo.prepared_presentation(11)


def test_missing_product_request_is_transaction_witness_and_not_repeated(repo):
    ingest(repo, "qué sabes de arroz jazmín")
    intent = Intent(action="product_query", lines=[IntentLine(description="arroz jazmín")])
    job = repo.prepare_dialogue(10, intent, "dry_run", now=NOW)
    assert job.snapshot.kind == "product"
    assert "Lo he anotado para revisar." in job.snapshot.facts[1].text
    assert repo.product_requests() == ["arroz jazmin"]
    assert repo.prepare_dialogue(10, None, "dry_run", now=NOW) == job


def test_replacement_snapshot_preserves_original_row_and_saved_destination(repo):
    prepare_add(repo)
    repo.finalize_presentation(11, Reply(text="ok"))
    steps = [("ahora arroz integral", Intent(action="mention_product", lines=[
        IntentLine(description="arroz integral")])), ("sustitúyelo", None), ("sí", None)]
    for number, (text, intent) in enumerate(steps, 12):
        ingest(repo, text, number)
        job = repo.prepare_dialogue(number, intent, "dry_run", now=NOW)
        repo.finalize_presentation(number, job.snapshot.fallback)
    original = repo.list_lines()[0]
    ingest(repo, "conserva la cantidad", 15)
    job = repo.prepare_dialogue(15, None, "dry_run", now=NOW)
    assert job.snapshot.kind == "replaced"
    assert job.snapshot.facts[0].text == "He sustituido arroz por arroz integral: 2 envases."
    saved = repo.list_lines()[0]
    assert saved.id == original.id and saved.revision == original.revision + 1
    assert repo.prepare_dialogue(15, None, "dry_run", now=NOW + timedelta(days=1)) == job
    assert repo.list_lines() == [saved]
