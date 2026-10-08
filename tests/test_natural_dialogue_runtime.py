"""Offline runtime acceptance: real inbox, reducer, SQLite and both HTTP boundaries."""

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from conversation import Conversation
from dialogue_requests import classify_request
from domain import IncomingMessage, Intent, IntentLine, Reply
from interpreter import OpenAIInterpreter
from ollama_interpreter import OllamaInterpreter
from ollama_replies import OllamaReplyWriter
from runtime import _CommandsOnly
from storage import Repository
from tests.dialogue_support import (
    Clock,
    dialogue_parts,
    feed,
    make_repo,
    order_count,
    seed_line,
    send,
)
from tests.fakes import FakeBot, FakeInterpreter, FakeOpenAI

NOW = datetime(2026, 10, 8, tzinfo=UTC)


@pytest.fixture(autouse=True)
def network_tripwire(monkeypatch):
    attempts = []
    async def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Unmocked HTTP boundary")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    yield
    assert not attempts, "Provider swallowed an unmocked network attempt"


class Models:
    def __init__(self):
        self.proposals = []
        self.drafts = []
        self.hostile = False
        self.cancel = False
        self.interpreter = OllamaInterpreter(transport=httpx.MockTransport(self.interpret))
        self.writer = OllamaReplyWriter("test", transport=httpx.MockTransport(self.write))

    @staticmethod
    def response(content):
        return httpx.Response(200, json={"done_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps(content)}})

    def interpret(self, request):
        payload = json.loads(request.content)
        context = json.loads(payload["messages"][1]["content"])
        self.proposals.append(context)
        source = classify_request(context["text"])
        intent = Intent(action="list") if self.hostile else (
            Intent(action=source.action, lines=[] if source.description is None else
                   [IntentLine(description=source.description)]) if source else Intent(action="clarify"))
        return self.response(intent.model_dump())

    def write(self, request):
        payload = json.loads(request.content)
        self.drafts.append(json.loads(payload["messages"][1]["content"]))
        if self.cancel:
            raise asyncio.CancelledError
        # Pick a schema-approved variant rather than relying on deterministic fallback.
        blocks = payload["format"]["properties"]["blocks"]["anyOf"][0]["prefixItems"]
        return self.response({"blocks": [{"role": b["properties"]["role"]["const"],
                                         "text": b["properties"]["text"]["enum"][0]}
                                        for b in blocks]})


def ingest(repo, text, number=100):
    message = IncomingMessage(update_id=number, user_id=7, chat_id=7, text=text)
    repo.ingest_batch([message], number + 1)
    return message


def state(repo):
    with sqlite3.connect(repo.path) as db:
        return db.execute("SELECT * FROM dialogue_state").fetchall()


def notices(repo, number):
    with sqlite3.connect(repo.path) as db:
        return db.execute("SELECT count(*) FROM outbox WHERE update_id=?", (number,)).fetchone()[0]


def test_capture_sequence_has_no_accidental_list_or_more_product(tmp_path):
    bot, models, clock = FakeBot(), Models(), Clock(NOW)
    parts, _ = dialogue_parts(tmp_path / "runtime.db", bot, clock, models.interpreter,
                              reply_writer=models.writer)
    repo = parts[1]
    for name in ("arroz", "pienso", "avena"):
        seed_line(repo, name, 2)
    before = repo.list_lines()
    for number, text in enumerate(("hols", "hola qué tal", "quiero más arroz", "cancelar",
                                   "añade más arroz", "cancelar", "dame mi lista"), 10):
        feed(parts, bot, number, text)
    assert repo.list_lines() == before and len(before) == 3
    assert all(name not in text for _, text in bot.sent[:2] for name in ("arroz", "pienso", "avena"))
    assert models.drafts[0]["kind"] == models.drafts[1]["kind"] == "greeting"
    assert all(c["text"] not in {"hols", "hola qué tal"} for c in models.proposals)
    assert models.proposals[1]["text"] == "añade más arroz"
    assert all(x.description != "más arroz" for x in repo.list_lines())
    assert all(x in bot.sent[-1][1] for x in ("arroz", "pienso", "avena"))


def test_pending_add_list_greeting_resume(tmp_path):
    repo, models, clock = make_repo(tmp_path), Models(), Clock(NOW)
    def turn(text):
        return send(repo, text, models.interpreter, clock=clock, reply_writer=models.writer)
    turn("necesito arroz jazmín")
    pending = state(repo)
    assert repo.list_lines() == []
    clock.advance(100)
    turn("dame mi lista")
    assert state(repo) == pending
    clock.advance(100)
    greeting = turn("hola")
    assert state(repo) == pending and "jazmín" not in greeting.text
    clock.advance(100)
    turn("qué sabes de pienso")
    assert state(repo) == pending
    turn("2")
    assert [(x.description, x.quantity) for x in repo.list_lines()] == [("arroz jazmín", 2)]


def test_compound_greeting_and_hostile_list_proposal(tmp_path):
    repo, models = make_repo(tmp_path), Models()
    seed_line(repo, "private product", 3)
    models.hostile = True
    greeting = send(repo, "hola", models.interpreter, clock=Clock(NOW), reply_writer=models.writer)
    assert "private product" not in greeting.text and models.proposals == []
    models.hostile = False
    send(repo, "Hola, necesito arroz", models.interpreter, clock=Clock(NOW), reply_writer=models.writer)
    assert models.proposals[-1]["text"] == "Hola, necesito arroz"
    assert repo.message_result(3)[0].text == "Hola, necesito arroz"
    assert repo.dialogue_state(7, 7, now=NOW).focus.description == "arroz"
    send(repo, "2", clock=Clock(NOW))
    assert repo.list_lines()[-1].description == "arroz"


def test_writer_http_error_keeps_committed_fallback_and_context(tmp_path):
    repo, models, clock = make_repo(tmp_path), Models(), Clock(NOW)
    writer = OllamaReplyWriter("test", transport=httpx.MockTransport(
        lambda request: httpx.Response(503)))
    reply = send(repo, "necesito arroz", models.interpreter, clock=clock, reply_writer=writer)
    assert "Todavía no" in reply.text and repo.list_lines() == []
    pending = state(repo)
    clock.advance(100)
    reply = send(repo, "hola", models.interpreter, clock=clock, reply_writer=writer)
    assert "Hola" in reply.text and "arroz" not in reply.text and state(repo) == pending
    send(repo, "2", clock=clock, reply_writer=writer)
    assert repo.list_lines()[0].quantity == 2


@pytest.mark.parametrize("provider", ["commands", "openai"])
def test_commands_buy_and_other_providers_unchanged_authority(tmp_path, provider):
    repo = make_repo(tmp_path)
    interpreter = (_CommandsOnly() if provider == "commands" else OpenAIInterpreter(
        FakeOpenAI(Intent(action="add", lines=[IntentLine(description="avena")])), "test"))
    send(repo, "/anadir 2 arroz", interpreter, clock=Clock(NOW))
    reply = send(repo, "/lista", interpreter, clock=Clock(NOW))
    assert repo.list_lines()[0].id in reply.text
    for text in ("hola /comprar", "hola compra lo pendiente"):
        send(repo, text, FakeInterpreter(Intent(action="buy")), clock=Clock(NOW))
    assert order_count(repo) == 0
    send(repo, "/anadir avena", interpreter, clock=Clock(NOW))
    assert len(repo.list_lines()) == 1
    send(repo, "2", interpreter, clock=Clock(NOW))
    assert len(repo.list_lines()) == 2
    if provider == "openai":
        send(repo, "necesito avena", interpreter, clock=Clock(NOW))
    send(repo, "/comprar", interpreter, clock=Clock(NOW))
    assert order_count(repo) == 1
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM presentation_jobs").fetchone()[0] == 0


def test_migrate_prepared_v1_recover_without_writer(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "v7.db")
    with sqlite3.connect(repo.path) as db:
        for number in range(1, 8):
            db.executescript((Path(__file__).parents[1] / f"migrations/{number:03}.sql").read_text())
    seed_line(repo, "historical rice", 2)
    message = ingest(repo, "necesito arroz")
    # Materialize the historical action, then model its pre-finalization v7 job.
    repo.apply_intent(100, Intent(action="add", lines=[IntentLine(description="arroz", quantity=2)]),
                      "dry_run")
    fallback = Reply(text="Historical exact reply with 2 envases.")
    snapshot = {"version": 1, "kind": "added", "facts": [{"key": "f0", "text": "Rice: 2 envases."}],
                "options": [], "question": None, "fallback": fallback.model_dump()}
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE inbox SET completed=0,reply_json=NULL WHERE update_id=100")
        db.execute("DELETE FROM outbox WHERE update_id=100")
        db.execute("INSERT INTO presentation_jobs VALUES (?,?,?,?,?)",
                   (100, 7, 7, json.dumps(snapshot), NOW.isoformat()))
        db.execute("INSERT INTO dialogue_state VALUES (?,?,?)", (7, 7, '{"old":"dialogue"}'))
    repo.migrate()
    assert state(repo) == []
    before = repo.list_lines()
    def forbidden(*args, **kwargs):
        raise AssertionError("Recovery must precede context/classifier/reducer")
    monkeypatch.setattr("conversation.classify_request", forbidden)
    for method in ("list_lines", "dialogue_state", "prepare_dialogue", "apply_dialogue"):
        monkeypatch.setattr(repo, method, forbidden)
    conversation = Conversation(repo, FakeInterpreter(), clock=forbidden)
    assert asyncio.run(conversation.handle(message, "dry_run")) == fallback
    assert asyncio.run(conversation.handle(message, "dry_run")) == fallback
    assert Repository(repo.path).list_lines() == before and notices(repo, 100) == 1


@pytest.mark.parametrize("operation", ["add", "increment"])
@pytest.mark.parametrize("failure", ["cancel_http", "outbox"])
def test_crashes_around_add_and_increment_commits(tmp_path, operation, failure):
    repo, models, clock = make_repo(tmp_path), Models(), Clock(NOW)
    if operation == "increment":
        seed_line(repo, "arroz", 2)
    send(repo, "necesito arroz" if operation == "add" else "quiero más arroz",
         models.interpreter, clock=clock, reply_writer=models.writer)
    if operation == "increment":
        send(repo, "3", clock=clock, reply_writer=models.writer)
    message = ingest(repo, "2" if operation == "add" else "sí")
    if failure == "cancel_http":
        models.cancel = True
        expected = asyncio.CancelledError
    else:
        with sqlite3.connect(repo.path) as db:
            db.execute("CREATE TRIGGER fail_outbox BEFORE INSERT ON outbox "
                       "BEGIN SELECT RAISE(ABORT,'injected outbox'); END")
        expected = sqlite3.IntegrityError
    with pytest.raises(expected):
        asyncio.run(Conversation(repo, models.interpreter, clock=clock,
                                 reply_writer=models.writer).handle(message, "dry_run"))
    committed, pending = repo.list_lines(), state(repo)
    assert committed[0].quantity == (2 if operation == "add" else 5)
    assert repo.message_result(100)[1] is None and notices(repo, 100) == 0
    if failure == "outbox":
        with sqlite3.connect(repo.path) as db:
            db.execute("DROP TRIGGER fail_outbox")
    clock.advance(2000)
    restarted = Repository(repo.path)
    reply = asyncio.run(Conversation(restarted, FakeInterpreter(), clock=clock).handle(message, "dry_run"))
    assert asyncio.run(Conversation(restarted, models.interpreter, clock=clock,
                                   reply_writer=models.writer).handle(message, "dry_run")) == reply
    assert restarted.list_lines() == committed and state(restarted) == pending
    assert notices(repo, 100) == 1


@pytest.mark.parametrize("damage", ["owner", "json"])
def test_owner_and_corrupt_state_fail_closed(tmp_path, damage):
    repo, models = make_repo(tmp_path), Models()
    message = ingest(repo, "hola")
    job = repo.prepare_dialogue(100, Intent(action="greet"), "dry_run", now=NOW)
    with sqlite3.connect(repo.path) as db:
        if damage == "owner":
            db.execute("UPDATE presentation_jobs SET user_id=8")
        else:
            db.execute("UPDATE presentation_jobs SET snapshot_json='broken'")
    with pytest.raises(ValueError):
        asyncio.run(Conversation(repo, models.interpreter, reply_writer=models.writer).handle(message, "dry_run"))
    assert models.proposals == models.drafts == [] and notices(repo, 100) == 0
    assert repo.list_lines() == [] and job.snapshot.kind == "greeting"


def test_foreign_owner_runtime_never_drafts_or_sends(tmp_path):
    from tests.test_end_to_end import cycles

    bot, models = FakeBot(), Models()
    parts, _ = dialogue_parts(tmp_path / "foreign.db", bot, Clock(NOW), models.interpreter,
                              reply_writer=models.writer)
    repo = parts[1]
    message = IncomingMessage(update_id=1, user_id=8, chat_id=8, text="hola")
    repo.ingest_batch([message], 2)
    with pytest.raises(PermissionError):
        cycles(parts, 1)
    assert bot.sent == [] and models.proposals == models.drafts == []
    assert repo.list_lines() == [] and notices(repo, 1) == 0


def test_corrupt_dialogue_state_cannot_authorize_pending_add(tmp_path):
    repo, models = make_repo(tmp_path), Models()
    send(repo, "necesito arroz", models.interpreter, clock=Clock(NOW), reply_writer=models.writer)
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE dialogue_state SET state_json='broken'")
    message = ingest(repo, "2")
    models.proposals.clear()
    models.drafts.clear()
    asyncio.run(Conversation(repo, models.interpreter, clock=Clock(NOW),
                             reply_writer=models.writer).handle(message, "dry_run"))
    assert repo.list_lines() == [] and repo.dialogue_state(7, 7, now=NOW) is None
    assert models.proposals == []


@pytest.mark.parametrize("operation", ["add", "increment"])
def test_bot_send_failure_restarts_without_reapplying_transition(tmp_path, operation, monkeypatch):
    from telegram.error import NetworkError

    from tests.test_end_to_end import cycles

    bot, models, clock = FakeBot(), Models(), Clock(NOW)
    path = tmp_path / "delivery.db"
    parts, _ = dialogue_parts(path, bot, clock, models.interpreter, reply_writer=models.writer)
    repo = parts[1]
    if operation == "increment":
        seed_line(repo, "arroz", 2)
    feed(parts, bot, 10, "necesito arroz" if operation == "add" else "quiero más arroz")
    if operation == "increment":
        feed(parts, bot, 11, "3")
    original_send = bot.send_message
    async def fail_send(**kwargs):
        raise NetworkError("offline send failure")
    monkeypatch.setattr(bot, "send_message", fail_send)
    bot.receive(12, "2" if operation == "add" else "sí")
    cycles(parts, 3)
    committed, pending = repo.list_lines(), state(repo)
    reply = repo.message_result(12)[1]
    assert committed[0].quantity == (2 if operation == "add" else 5)
    assert reply is not None and notices(repo, 12) == 1
    before_calls = (len(models.proposals), len(models.drafts))
    clock.advance(2000)
    monkeypatch.setattr(bot, "send_message", original_send)
    restarted, _ = dialogue_parts(path, bot, clock, models.interpreter, reply_writer=models.writer)
    cycles(restarted, 2)
    assert restarted[1].list_lines() == committed and state(repo) == pending
    assert before_calls == (len(models.proposals), len(models.drafts))
    assert sum(text == reply.text for _, text in bot.sent) == 1
