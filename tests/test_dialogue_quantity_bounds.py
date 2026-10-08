"""SQLite quantity boundaries through real contextual transactions."""

import asyncio
import sqlite3
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from conversation import Conversation
from dialogue import DialogueAnswer, DialogueMutation, DialogueState, parse_answer
from domain import Intent, IntentLine
from tests.dialogue_support import Clock, make_repo, propose, seed_line, send
from tests.fakes import FakeInterpreter


def pending_quantity(repo, clock, replacement):
    send(repo, "/anadir arroz", clock=clock)
    if replacement:
        send(repo, "2", clock=clock)
        send(repo, "ahora pasta", propose("pasta", "mention_product"), clock=clock)
        send(repo, "sustitúyelo", clock=clock)
        send(repo, "sí", clock=clock)
    return repo.dialogue_state(7, 7, now=clock())


@pytest.mark.parametrize("replacement", [False, True])
@pytest.mark.parametrize("suffix", ["", " paquetes"])
def test_overflow_answer_completes_clarification_without_changes(tmp_path, replacement, suffix):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 1, tzinfo=UTC))
    state = pending_quantity(repo, clock, replacement)
    rows = repo.list_lines()
    notices = repo.pending_notices()
    clock.advance(30)
    reply = send(repo, "9223372036854775808" + suffix, clock=clock)
    assert reply.text.startswith("Indica la cantidad total de envases para " if replacement else "¿Cuántos envases de arroz")
    assert repo.list_lines() == rows
    assert repo.dialogue_state(7, 7, now=clock()) == state
    assert repo.pending_messages() == []
    assert len(repo.pending_notices()) == len(notices) + 1
    with sqlite3.connect(repo.path) as db:
        update_id = db.execute("SELECT max(update_id) FROM inbox").fetchone()[0]
        payload = db.execute("SELECT reply_json FROM outbox WHERE update_id=?", (update_id,)).fetchone()[0]
    assert payload == reply.model_dump_json()
    message, completed = repo.message_result(update_id)
    assert completed == reply
    clock.advance(30)
    assert asyncio.run(Conversation(repo, FakeInterpreter(), clock=clock).handle(message, "dry_run")) == reply
    assert repo.dialogue_state(7, 7, now=clock()) == state
    assert len(repo.pending_notices()) == len(notices) + 1
    assert parse_answer("9223372036854775808" + suffix, state, now=clock()) is None
    send(repo, "3 paquetes", clock=clock)
    assert [(l.description, l.quantity) for l in repo.list_lines()] == [
        ("pasta" if replacement else "arroz", 3),
    ]


@pytest.mark.parametrize("replacement", [False, True])
def test_maximum_sqlite_quantity_is_persisted(tmp_path, replacement):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 1, tzinfo=UTC))
    pending_quantity(repo, clock, replacement)
    reply = send(repo, "9223372036854775807 paquetes", clock=clock)
    assert "9223372036854775807 paquetes" in reply.text
    assert repo.list_lines()[0].quantity == 9223372036854775807
    assert repo.pending_messages() == []


@pytest.mark.parametrize("command", ["/anadir 9223372036854775808 pasta", "añade 9223372036854775808 pasta", "/cantidad {id} 9223372036854775808"])
def test_command_quantity_overflow_preserves_pending_dialogue(tmp_path, command):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 1, tzinfo=UTC))
    existing = seed_line(repo, "avena", 1)
    state = pending_quantity(repo, clock, False)
    rows = repo.list_lines()
    clock.advance(30)
    reply = send(repo, command.format(id=existing.id), clock=clock)
    assert "cantidad entera" in reply.text
    assert repo.list_lines() == rows
    assert repo.dialogue_state(7, 7, now=clock()) == state
    assert repo.pending_messages() == []


def test_model_quantity_cannot_become_a_contextual_proposal(tmp_path):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 1, tzinfo=UTC))
    state = pending_quantity(repo, clock, False)
    rows = repo.list_lines()
    clock.advance(30)
    model = FakeInterpreter(Intent(action="mention_product", lines=[
        IntentLine(description="pasta", quantity=9223372036854775808),
    ]))
    send(repo, "ahora pasta", model, clock=clock)
    assert repo.list_lines() == rows
    assert repo.dialogue_state(7, 7, now=clock()) == state
    assert repo.pending_messages() == []


@pytest.mark.parametrize("contract,fields", [
    (DialogueAnswer, {"kind": "quantity", "quantity": 9223372036854775808}),
    (DialogueMutation, {"kind": "add", "quantity": 9223372036854775808}),
])
def test_contextual_quantity_contracts_reject_sqlite_overflow(contract, fields):
    with pytest.raises(ValidationError):
        contract(**fields)


def test_persisted_proposal_contract_rejects_sqlite_overflow(tmp_path):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 1, tzinfo=UTC))
    state = pending_quantity(repo, clock, False)
    with pytest.raises(ValidationError):
        DialogueState.model_validate_json(state.model_copy(update={
            "proposal_quantity": 9223372036854775808,
        }).model_dump_json())
