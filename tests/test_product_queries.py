import asyncio
import sqlite3

import pytest

from conversation import Conversation
from domain import IncomingMessage, Intent, IntentLine
from storage import Repository
from tests.fakes import FakeInterpreter


@pytest.fixture
def repo(tmp_path):
    result = Repository(tmp_path / "products.db")
    result.migrate()
    return result


def send(repo, text, intent, *, update_id=None):
    if update_id is None:
        with sqlite3.connect(repo.path) as db:
            update_id = db.execute("SELECT coalesce(max(update_id), 0) + 1 FROM inbox").fetchone()[0]
    message = IncomingMessage(update_id=update_id, user_id=7, chat_id=7, text=text)
    repo.ingest_batch([message], update_id + 1)
    interpreter = intent if hasattr(intent, "parse") else FakeInterpreter(intent)
    return asyncio.run(Conversation(repo, interpreter).handle(message, "dry_run"))


def query(name):
    return Intent(action="product_query", lines=[IntentLine(description=name)])


def test_list_from_model_uses_persisted_lines_after_restart(repo):
    send(repo, "/anadir 2 arroz", None)
    reopened = Repository(repo.path)
    reopened.migrate()
    reply = send(reopened, "¿qué hay en mi lista?", Intent(action="list"))
    assert "arroz" in reply.text
    assert "2" in reply.text
    assert reopened.list_lines()[0].id in reply.text


def test_product_query_uses_two_dated_observations_not_current_offers(repo):
    reply = send(repo, "¿qué pañales Dodot vimos?", query("pañales Dodot"))
    assert "nappy" in reply.text
    assert "mercadona" in reply.text
    assert "https://nappy.es/" in reply.text
    assert "https://tienda.mercadona.es/" in reply.text
    assert "2026-09-27" in reply.text
    assert "2026-09-28" in reply.text
    assert "46,87" in reply.text
    assert "16,95" in reply.text
    assert "precio" in reply.text.lower() and "stock" in reply.text.lower()
    assert "actual" in reply.text.lower()
    assert repo.product_requests() == []


def test_product_observation_reports_unknown_stock_separately_from_freshness(repo):
    reply = send(repo, "¿tenemos ficha de Blemil?", query("Blemil"))
    assert "2026-09-27" in reply.text
    assert "stock no observado" in reply.text.lower()
    assert "stock no actuales" in reply.text.lower()


def test_product_observation_reports_dated_available_stock(repo):
    reply = send(repo, "¿qué pañales Dodot vimos?", query("pañales Dodot"))
    assert "stock observado disponible" in reply.text.lower()
    assert "stock no observado" in reply.text.lower()


def test_missing_product_is_deduplicated_after_replay_and_restart(repo):
    first = send(repo, "¿qué sabes de arroz?", query("arroz"))
    reopened = Repository(repo.path)
    reopened.migrate()
    assert "arroz" in first.text.lower()
    assert "ficha" in first.text.lower()
    assert send(reopened, "¿qué sabes de arroz?", query("arroz"), update_id=1) == first
    send(reopened, "¿qué sabes de arroz?", query("arroz"))
    assert reopened.product_requests() == ["arroz"]
    assert len(reopened.pending_notices()) == 2


def test_generic_question_never_creates_product_backlog(repo):
    send(repo, "¿qué puedes hacer?", query("arroz"))
    assert repo.product_requests() == []


def test_internal_question_mark_does_not_enter_backlog(repo):
    reply = send(repo, "¿qué sabes de arroz? compra?", query("arroz? compra"))
    assert "aclara" in reply.text.lower() or "claro" in reply.text.lower()
    assert repo.product_requests() == []
    assert repo.list_lines() == []


@pytest.mark.parametrize(
    "text,intent",
    [
        ("no quiero saber de arroz", [IntentLine(description="arroz")]),
        ('"¿qué sabes de arroz?"', [IntentLine(description="arroz")]),
        ("¿qué sabes de arroz y pasta?", [IntentLine(description="arroz")]),
        ("¿qué sabes de arroz? https://evil.example", [IntentLine(description="arroz")]),
        ("¿qué sabes de arroz?", [IntentLine(description="arroz", line_id="fabricado")]),
        ("¿qué sabes de arroz?", [IntentLine(description="arroz", quantity=3)]),
        ("¿qué sabes de arroz?", [IntentLine(description="arroz", url="https://evil.example")]),
        ("¿qué sabes de pienso de pollo?", [IntentLine(description="pienso")]),
        ("¿qué sabes de arroz?", [IntentLine(description="arroz"), IntentLine(description="pasta")]),
    ],
)
def test_untrusted_product_query_cannot_change_backlog_or_list(repo, text, intent):
    before = repo.list_lines()
    reply = send(repo, text, Intent(action="product_query", lines=intent))
    assert "aclara" in reply.text.lower() or "claro" in reply.text.lower()
    assert repo.product_requests() == []
    assert repo.list_lines() == before


def test_backlog_inbox_and_outbox_roll_back_together(repo):
    with sqlite3.connect(repo.path) as db:
        db.executescript("""CREATE TRIGGER reject_notice BEFORE INSERT ON outbox
        BEGIN SELECT RAISE(ABORT, 'injected'); END;""")
    with pytest.raises(sqlite3.IntegrityError):
        send(repo, "¿qué sabes de arroz?", query("arroz"))
    assert repo.product_requests() == []
    assert repo.pending_notices() == []
    assert repo.pending_messages()[0].update_id == 1
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER reject_notice")
    send(repo, "¿qué sabes de arroz?", query("arroz"), update_id=1)
    assert repo.product_requests() == ["arroz"]
    assert len(repo.pending_notices()) == 1


def test_commands_skip_model(repo):
    class ForbiddenInterpreter:
        calls = 0

        async def parse(self, text, lines):
            self.calls += 1
            return query("arroz")

    interpreter = ForbiddenInterpreter()
    send(repo, "/anadir 2 arroz", interpreter)
    send(repo, "/lista", interpreter)
    assert interpreter.calls == 0
    assert repo.product_requests() == []
