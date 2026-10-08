"""Confirmed increments against real isolated SQLite rows."""

import json
import sqlite3
from datetime import UTC, datetime

import pytest

from dialogue import MAX_QUANTITY
from dialogue_controller import reduce_dialogue
from domain import IncomingMessage, Intent
from interpreter import parse_command, quantity
from tests.dialogue_support import Clock, make_repo, seed_line, send


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


@pytest.fixture
def clock():
    return Clock(datetime(2026, 10, 1, tzinfo=UTC))


def pending(repo, clock, name="arroz"):
    send(repo, "añade más " + name, clock=clock)
    return repo.dialogue_state(7, 7, now=clock())


def test_two_rice_entries_select_then_delta_then_confirm(repo, clock):
    first = seed_line(repo, "arroz", 1)
    second = seed_line(repo, "ARROZ", 2)
    seed_line(repo, "arroz integral")
    before = repo.list_lines()
    state = pending(repo, clock)
    assert state.question == "select_line"
    assert {r.id for r in state.candidates} == {first.id, second.id}
    send(repo, str(next(i for i, r in enumerate(state.candidates, 1) if r.id == first.id)), clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).question == "increment_quantity"
    reply = send(repo, "2", clock=clock)
    state = repo.dialogue_state(7, 7, now=clock())
    assert (state.base_quantity, state.additional_quantity, state.proposal_quantity) == (1, 2, 3)
    assert state.question == "confirm_increment" and "3" in reply.text
    assert repo.list_lines() == before
    send(repo, "4", clock=clock)
    assert repo.list_lines() == before
    send(repo, "sí", clock=clock)
    saved = next(l for l in repo.list_lines() if l.id == first.id)
    assert saved == first.model_copy(update={"quantity": 3, "revision": first.revision + 1})
    state = repo.dialogue_state(7, 7, now=clock())
    assert state.focus.line.id == saved.id and state.focus.line.revision == saved.revision
    assert state.pending_kind is state.question is state.base_quantity is state.additional_quantity is None
    assert state.proposal_quantity is None and not state.increment_confirmed
    send(repo, "sí", clock=clock)
    assert next(l for l in repo.list_lines() if l.id == first.id) == saved


def test_missing_product_offers_pending_add(repo, clock):
    state = pending(repo, clock)
    assert state.question == "increment_missing" and state.options == ("add",)
    assert repo.list_lines() == []
    send(repo, "añádelo", clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).question == "add_quantity"
    assert repo.list_lines() == []
    send(repo, "2", clock=clock)
    assert repo.list_lines()[0].quantity == 2


def test_unknown_base_offers_total_not_zero(repo, clock):
    line = seed_line(repo, "arroz")
    state = pending(repo, clock)
    assert state.question == "increment_unknown" and "change_quantity" in state.options
    send(repo, "cambiar cantidad", clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).question == "quantity"
    assert repo.list_lines() == [line]
    send(repo, "3", clock=clock)
    assert repo.list_lines()[0].quantity == 3


@pytest.mark.parametrize("finish", ["no", "cancelar", "expired"])
def test_no_cancel_and_expired_do_not_write(repo, clock, finish):
    seed_line(repo, "arroz", 1)
    pending(repo, clock)
    send(repo, "2", clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).question == "confirm_increment"
    before = repo.list_lines()
    if finish == "expired":
        clock.advance(900)
    send(repo, "sí" if finish == "expired" else finish, clock=clock)
    assert repo.list_lines() == before
    assert repo.dialogue_state(7, 7, now=clock()) is None


@pytest.mark.parametrize("change", ["base", "revision", "deleted", "reserved"])
def test_changed_base_missing_or_reserved_invalidates_yes(repo, clock, change):
    line = seed_line(repo, "arroz", 1)
    pending(repo, clock)
    send(repo, "2", clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).question == "confirm_increment"
    if change == "reserved":
        update = 50
        repo.ingest_batch([IncomingMessage(update_id=update, user_id=7, chat_id=7, text="/comprar")], 51)
        repo.apply_intent(update, Intent(action="buy"), "dry_run")
    else:
        with sqlite3.connect(repo.path) as db:
            if change == "deleted":
                db.execute("DELETE FROM list_lines WHERE id=?", (line.id,))
            else:
                db.execute("UPDATE list_lines SET " + ("quantity=7" if change == "base" else "revision=revision+1") + " WHERE id=?", (line.id,))
    before = repo.list_lines()
    send(repo, "sí", clock=clock)
    assert repo.list_lines() == before
    assert repo.dialogue_state(7, 7, now=clock()) is None


@pytest.mark.parametrize("text", ["1", "9" * 5000, "1.5", "2 kg", "2 unidades"])
def test_overflow_units_and_diaper_packs(repo, clock, text):
    seed_line(repo, "pañales", MAX_QUANTITY)
    pending(repo, clock, "pañales")
    state = repo.dialogue_state(7, 7, now=clock())
    assert state.question == "increment_quantity"
    before = repo.list_lines()
    send(repo, text, clock=clock)
    assert repo.list_lines() == before
    assert repo.dialogue_state(7, 7, now=clock()) == state
    assert repo.pending_messages() == []


def test_explicit_diaper_packages(repo, clock):
    seed_line(repo, "pañales", 1)
    pending(repo, clock, "pañales")
    send(repo, "2 paquetes", clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).proposal_quantity == 3
    send(repo, "confirmo", clock=clock)
    assert repo.list_lines()[0].quantity == 3


def test_sum_overflow_preserves_question_and_valid_maximum_total(repo, clock):
    seed_line(repo, "arroz", MAX_QUANTITY - 1)
    state = pending(repo, clock)
    before = repo.list_lines()
    reply = send(repo, "2", clock=clock)
    assert "rango permitido" in reply.text
    assert repo.dialogue_state(7, 7, now=clock()) == state
    assert repo.list_lines() == before
    send(repo, "1", clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).proposal_quantity == MAX_QUANTITY
    send(repo, "sí", clock=clock)
    assert repo.list_lines()[0].quantity == MAX_QUANTITY


def test_queries_greeting_and_alias_do_not_reauthorize_or_renew_increment(repo, clock):
    seed_line(repo, "arroz", 1)
    pending(repo, clock)
    send(repo, "2", clock=clock)
    state = repo.dialogue_state(7, 7, now=clock())
    before = repo.list_lines()
    clock.advance(30)
    for text in ("añádelo", "/lista", "hola"):
        send(repo, text, clock=clock)
        assert repo.dialogue_state(7, 7, now=clock()) == state
        assert repo.list_lines() == before


@pytest.mark.parametrize("field,value", [("increment_confirmed", False), ("base_quantity", 2),
                                       ("additional_quantity", 3), ("proposal_quantity", 4)])
def test_final_sql_revalidates_copied_state(repo, clock, monkeypatch, field, value):
    seed_line(repo, "arroz", 1)
    pending(repo, clock)
    send(repo, "2", clock=clock)
    before = repo.list_lines()
    state = repo.dialogue_state(7, 7, now=clock())

    def corrupt(*args, **kwargs):
        decision = reduce_dialogue(*args, **kwargs)
        return decision.model_copy(update={"state": decision.state.model_copy(update={field: value})})

    monkeypatch.setattr("dialogue_storage.reduce_dialogue", corrupt)
    with pytest.raises(ValueError):
        send(repo, "sí", clock=clock)
    assert repo.list_lines() == before
    assert repo.dialogue_state(7, 7, now=clock()) == state


def test_final_sql_requires_exactly_one_updated_row(repo, clock):
    seed_line(repo, "arroz", 1)
    pending(repo, clock)
    send(repo, "2", clock=clock)
    before = repo.list_lines()
    with sqlite3.connect(repo.path) as db:
        db.execute("CREATE TRIGGER ignore_increment BEFORE UPDATE ON list_lines BEGIN SELECT RAISE(IGNORE); END")
    with pytest.raises(ValueError, match="exactly one"):
        send(repo, "sí", clock=clock)
    assert repo.list_lines() == before
    assert repo.dialogue_state(7, 7, now=clock()).question == "confirm_increment"


def test_prepared_v1_increment_facts_recover_without_reapplying(repo, clock):
    line = seed_line(repo, "arroz", 1)

    def prepare(update_id, text):
        repo.ingest_batch([IncomingMessage(update_id=update_id, user_id=7, chat_id=7, text=text)], update_id + 1)
        return repo.prepare_dialogue(update_id, None, "dry_run", now=clock())

    question = prepare(40, "quiero más arroz")
    assert question.snapshot.version == 1 and "adicionales" in question.snapshot.question
    repo.finalize_presentation(40, question.snapshot.fallback)
    confirmation = prepare(41, "2")
    assert "2 envases" in confirmation.snapshot.question and "de 1 a 3" in confirmation.snapshot.question
    assert repo.list_lines() == [line]
    repo.finalize_presentation(41, confirmation.snapshot.fallback)
    result = prepare(42, "sí")
    assert result.snapshot.version == 1 and result.snapshot.kind == "updated"
    assert "2 envases" in result.snapshot.facts[0].text and "de 1 a 3" in result.snapshot.fallback.text
    saved = repo.list_lines()
    assert saved[0].quantity == 3 and saved[0].revision == line.revision + 1
    clock.advance(900)
    assert repo.prepare_dialogue(42, None, "dry_run", now=clock()) == result
    assert repo.finalize_presentation(42, result.snapshot.fallback) == result.snapshot.fallback
    assert repo.list_lines() == saved


def test_corrupt_increment_quantity_with_unknown_base_is_discarded(repo, clock):
    line = seed_line(repo, "arroz")
    pending(repo, clock)
    with sqlite3.connect(repo.path) as db:
        payload = json.loads(db.execute("SELECT state_json FROM dialogue_state").fetchone()[0])
        payload.update(question="increment_quantity", options=[])
        db.execute("UPDATE dialogue_state SET state_json=?", (json.dumps(payload),))
    send(repo, "2", clock=clock)
    assert repo.list_lines() == [line]
    assert repo.dialogue_state(7, 7, now=clock()) is None


@pytest.mark.parametrize("number", [str(MAX_QUANTITY + 1), "9" * 5000])
@pytest.mark.parametrize("template", ["/cantidad id {}", "/anadir {} arroz", "añade {} arroz"])
def test_bounded_numeric_commands(number, template):
    assert parse_command(template.format(number), []).action == "clarify"
    assert quantity(number) is None


def test_replay_rollback_and_snapshot_unchanged(repo, clock):
    line = seed_line(repo, "arroz", 1)
    repo.ingest_batch([IncomingMessage(update_id=20, user_id=7, chat_id=7, text="/comprar")], 21)
    order_reply = repo.apply_intent(20, Intent(action="buy"), "dry_run")
    historical = repo.get_order(order_reply.order_id)
    with sqlite3.connect(repo.path) as db:
        db.execute("DELETE FROM reservations")
    pending(repo, clock)
    send(repo, "2", clock=clock)
    with sqlite3.connect(repo.path) as db:
        db.execute("CREATE TRIGGER abort_increment BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT,'injected'); END")
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        send(repo, "sí", clock=clock, update_id=30)
    assert repo.list_lines() == [line]
    assert repo.dialogue_state(7, 7, now=clock()).question == "confirm_increment"
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER abort_increment")
    reply = send(repo, "sí", clock=clock, update_id=30)
    saved = repo.list_lines()
    assert saved[0].quantity == 3 and saved[0].revision == line.revision + 1
    assert send(repo, "sí", clock=clock, update_id=30) == reply
    assert repo.list_lines() == saved
    assert repo.get_order(order_reply.order_id) == historical
