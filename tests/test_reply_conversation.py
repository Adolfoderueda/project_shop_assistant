import asyncio
import sqlite3
from datetime import UTC, datetime

import pytest

from conversation import Conversation
from domain import IncomingMessage, Intent, IntentLine
from presentation import DraftBlock, ReplyDraft
from storage import Repository
from tests.dialogue_support import Clock, make_repo, order_count, propose, seed_line, send
from tests.fakes import FakeInterpreter


class Writer:
    def __init__(self, callback=None):
        self.snapshots = []
        self.callback = callback

    async def draft(self, snapshot):
        self.snapshots.append(snapshot)
        if self.callback:
            self.callback(snapshot)
        blocks = ([DraftBlock(role="lead", text="Vamos por partes")]
                  if snapshot.version == 1 else [])
        blocks.extend(DraftBlock(role="fact", text="{{" + f.key + "}}") for f in snapshot.facts)
        if snapshot.question is not None:
            blocks.append(DraftBlock(role="question", text="{{q}}"))
        blocks.extend(DraftBlock(role="option", text="{{" + o.key + "}}") for o in snapshot.options)
        return ReplyDraft(blocks=tuple(blocks))


class ForbiddenInterpreter:
    async def parse(self, *_):
        pytest.fail("prepared/closed work must not be interpreted")


def message(repo, text, number=10):
    result = IncomingMessage(update_id=number, user_id=7, chat_id=7, text=text)
    repo.ingest_batch([result], number + 1)
    return result


def handle(repo, text, writer, interpreter=None, *, number=10, clock=None):
    msg = message(repo, text, number)
    return asyncio.run(Conversation(repo, interpreter or FakeInterpreter(), clock=clock,
                                   reply_writer=writer).handle(msg, "dry_run"))


def test_closed_quantity_uses_writer_not_interpreter(tmp_path):
    repo = make_repo(tmp_path)
    send(repo, "necesito arroz", propose("arroz"))
    writer = Writer(lambda snapshot: (
        repo.list_lines()[0].quantity == 2 or pytest.fail("quantity was not committed")))
    reply = handle(repo, "2", writer, ForbiddenInterpreter())
    assert writer.snapshots[0].kind == "added"
    assert "2 envases" in reply.text and reply.text.startswith("He añadido")
    assert repo.list_lines()[0].revision == 1
    assert repo.message_result(10)[1] == reply
    assert order_count(repo) == 0


def test_all_natural_classes_reach_writer(tmp_path):
    repo = make_repo(tmp_path)
    writer = Writer()
    sequence = [
        ("necesito arroz", propose("arroz")),
        ("2", ForbiddenInterpreter()),
        ("lista", None),
        ("qué sabes de pasta?", propose("pasta", "product_query")),
        ("no entiendo", None),
        ("cancelar", ForbiddenInterpreter()),
        ("ahora pasta", propose("pasta", "mention_product")),
        ("añádelo", ForbiddenInterpreter()),
        ("3", ForbiddenInterpreter()),
        ("ahora avena", propose("avena", "mention_product")),
        ("sustitúyelo", ForbiddenInterpreter()),
        ("sí", ForbiddenInterpreter()),
        ("4", ForbiddenInterpreter()),
        ("/anadir arroz", None),
        ("cambiar cantidad", ForbiddenInterpreter()),
        ("3", ForbiddenInterpreter()),
    ]
    for number, (text, interpreter) in enumerate(sequence, 10):
        handle(repo, text, writer, interpreter, number=number)
    assert len(writer.snapshots) == len(sequence) - 1  # Slash command bypasses the writer.
    assert {s.kind for s in writer.snapshots} == {
        "added", "updated", "list", "product", "clarify", "cancelled", "question", "replaced",
        "pending_add",
    }
    assert [(line.description, line.quantity) for line in repo.list_lines()] == [
        ("arroz", 3), ("avena", 4),
    ]
    assert order_count(repo) == 0


@pytest.mark.parametrize("text", ["/lista", "/anadir arroz", "/unknown", "/comprar",
                                       "compra lo pendiente", "compra la lista"])
def test_slash_purchase_and_notices_bypass_writer(tmp_path, text):
    repo = make_repo(tmp_path / "writer")
    baseline = make_repo(tmp_path / "baseline")
    # Incomplete purchase and operational notices must keep their deterministic reply.
    seed_line(repo, "arroz")
    seed_line(baseline, "arroz")
    writer = Writer()
    reply = handle(repo, text, writer)
    expected = send(baseline, text, update_id=10)
    # Slash list contains independently generated row IDs.
    if text == "/lista":
        assert reply.text.replace(repo.list_lines()[0].id, "ID") == expected.text.replace(
            baseline.list_lines()[0].id, "ID")
    else:
        assert reply == expected
    assert writer.snapshots == []
    assert order_count(repo) == 0


def test_recover_prepared_before_any_interpretation(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 8, tzinfo=UTC))
    msg = message(repo, "necesito arroz")
    prepared = repo.prepare_dialogue(10, Intent(action="add", lines=[
        IntentLine(description="arroz")]), "dry_run", now=clock())
    state = repo.dialogue_state(7, 7, now=clock())
    clock.advance(100)
    restarted = Repository(repo.path)
    for name in ("apply_dialogue", "prepare_dialogue", "list_lines", "dialogue_state"):
        monkeypatch.setattr(restarted, name, lambda *_a, **_k: pytest.fail("replayed transition"))
    reply = asyncio.run(Conversation(restarted, ForbiddenInterpreter(), clock=clock).handle(
        msg, "dry_run"))
    assert reply == prepared.snapshot.fallback
    assert repo.dialogue_state(7, 7, now=clock()) == state
    assert repo.list_lines() == []
    assert len(repo.pending_notices()) == 1


def test_cancel_between_commits_and_replay_after_finalization(tmp_path):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 8, tzinfo=UTC))
    msg = message(repo, "necesito arroz")

    def cancel(_):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(Conversation(repo, propose("arroz"), clock=clock,
                                 reply_writer=Writer(cancel)).handle(msg, "dry_run"))
    state = repo.dialogue_state(7, 7, now=clock())
    assert repo.message_result(10)[1] is None and repo.pending_notices() == []
    assert repo.prepared_presentation(10) is not None
    clock.advance(100)
    writer = Writer()
    restarted = Conversation(Repository(repo.path), ForbiddenInterpreter(), clock=clock,
                             reply_writer=writer)
    reply = asyncio.run(restarted.handle(msg, "dry_run"))
    assert asyncio.run(restarted.handle(msg, "dry_run")) == reply
    assert len(writer.snapshots) == 1
    assert repo.dialogue_state(7, 7, now=clock()) == state
    assert len(repo.pending_notices()) == 1 and repo.list_lines() == []


def test_mutated_store_after_prepare_does_not_change_facts(tmp_path):
    repo = make_repo(tmp_path)

    def mutate(_):
        with sqlite3.connect(repo.path) as db:
            db.execute("UPDATE list_lines SET description='changed',quantity=99,revision=revision+1")

    reply = handle(repo, "añade 2 arroz", Writer(mutate))
    assert "arroz" in reply.text and "changed" not in reply.text and "99" not in reply.text
    assert repo.list_lines()[0].description == "changed"


@pytest.mark.parametrize("failure", ["exception", "none", "contradiction", "forged", "overbudget"])
def test_failed_writer_or_validation_uses_clear_fallback(tmp_path, failure):
    repo = make_repo(tmp_path)

    class FailedWriter(Writer):
        async def draft(self, snapshot):
            if failure == "exception":
                raise RuntimeError("private error")
            if failure == "none":
                return None
            if failure == "forged":
                return ReplyDraft(blocks=()).model_copy(update={"blocks": "corrupt"})
            text = "x" * 2001 if failure == "overbudget" else "No se ha añadido {{f0}}"
            return ReplyDraft(blocks=(DraftBlock(role="fact", text=text),))

    if failure == "forged":
        with pytest.warns(UserWarning, match="Pydantic serializer warnings"):
            reply = handle(repo, "necesito arroz", FailedWriter(), propose("arroz"))
    else:
        reply = handle(repo, "necesito arroz", FailedWriter(), propose("arroz"))
    assert reply == repo.prepared_presentation(10).snapshot.fallback
    assert "private error" not in reply.text
    assert repo.message_result(10)[1] == reply and len(repo.pending_notices()) == 1


def test_no_write_transaction_during_http(tmp_path):
    repo = make_repo(tmp_path)
    second = Repository(repo.path)

    def write(snapshot):
        assert second.list_lines() == []
        assert second.dialogue_state(7, 7, now=datetime.now(UTC)).focus.description == "arroz"
        assert second.message_result(10)[1] is None
        with second._connection(write=True) as db:
            db.execute("INSERT INTO meta(key,value) VALUES ('writer_probe','ok')")

    handle(repo, "necesito arroz", Writer(write), propose("arroz"))
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT value FROM meta WHERE key='writer_probe'").fetchone() == ("ok",)


def test_durable_errors_and_inbox_mismatch_are_not_writer_failures(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    writer = Writer()
    msg = message(repo, "necesito arroz")
    convo = Conversation(repo, propose("arroz"), reply_writer=writer)
    with pytest.raises(ValueError, match="inbox"):
        asyncio.run(convo.handle(msg.model_copy(update={"text": "different"}), "dry_run"))
    monkeypatch.setattr(repo, "prepared_presentation", lambda _: (_ for _ in ()).throw(
        sqlite3.OperationalError("durable failure")))
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(convo.handle(msg, "dry_run"))
    assert writer.snapshots == []


def test_snapshot_over_budget_bypasses_writer_without_truncating(tmp_path):
    repo = make_repo(tmp_path)
    for number in range(21):
        seed_line(repo, f"arroz integral marca {number}", 2)
    writer = Writer()
    reply = handle(repo, "lista", writer, number=30)
    assert writer.snapshots == []
    assert reply == repo.prepared_presentation(30).snapshot.fallback
    assert all(line.description in reply.text for line in repo.list_lines())


def test_writer_time_does_not_renew_ttl_and_finalize_error_stays_pending(tmp_path):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 8, tzinfo=UTC))
    writer = Writer(lambda _: clock.advance(100))
    handle(repo, "necesito arroz", writer, propose("arroz"), clock=clock)
    state = repo.dialogue_state(7, 7, now=clock())
    clock.advance(800)
    assert state is not None and repo.dialogue_state(7, 7, now=clock()) is None
    with sqlite3.connect(repo.path) as db:
        db.executescript("CREATE TRIGGER reject_notice BEFORE INSERT ON outbox BEGIN "
                         "SELECT RAISE(ABORT, 'injected'); END;")
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        handle(repo, "lista", writer, number=11, clock=clock)
    assert repo.prepared_presentation(11) is not None
    assert repo.message_result(11)[1] is None and len(repo.pending_notices()) == 1
