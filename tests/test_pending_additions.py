import json
import sqlite3
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dialogue import (
    DIALOGUE_TTL,
    DialogueAnswer,
    DialogueMutation,
    DialogueState,
    LineRef,
    ProductMention,
    parse_answer,
)
from dialogue_additions import answer_addition
from dialogue_controller import reduce_dialogue
from domain import IncomingMessage, Intent, IntentLine
from storage import Repository
from tests.dialogue_support import Clock, make_repo, seed_line, send


@pytest.mark.parametrize("change", [
    {"question": "quantity"}, {"duplicate_confirmed": True, "candidates": ()},
    {"focus": ProductMention(description="arroz", source_update_id=1, line=LineRef(id="a", revision=1))},
    {"target": LineRef(id="a", revision=1)}, {"increment_confirmed": True},
    {"base_quantity": 1}, {"additional_quantity": 1},
])
def test_pending_contract_rejects_saved_refs_or_mixed_permissions(change):
    now = datetime(2026, 10, 8, tzinfo=UTC)
    values = {"user_id": 7, "chat_id": 7, "pending_kind": "add", "question": "add_quantity",
              "focus": ProductMention(description="arroz", source_update_id=1),
              "updated_at": now, "expires_at": now + DIALOGUE_TTL}
    with pytest.raises(ValidationError):
        DialogueState(**(values | change))


def test_increment_contract_and_closed_answers():
    now = datetime(2026, 10, 8, tzinfo=UTC)
    target = LineRef(id="a", revision=1)
    state = DialogueState(user_id=7, chat_id=7, pending_kind="increment", question="confirm_increment",
        focus=ProductMention(description="arroz", source_update_id=1, line=target), target=target,
        base_quantity=2, additional_quantity=3, proposal_quantity=5,
        updated_at=now, expires_at=now + DIALOGUE_TTL)
    assert parse_answer("sí", state, now=now).kind == "confirm"
    assert parse_answer("no", state, now=now).kind == "reject"
    assert parse_answer("2", state, now=now) is None
    with pytest.raises(ValidationError):
        DialogueState.model_validate_json(state.model_copy(update={"proposal_quantity": 6}).model_dump_json())
    mutation = DialogueMutation(kind="increment", target=target, description="arroz",
                                expected_base=2, additional_quantity=3, quantity=5)
    with pytest.raises(ValidationError):
        DialogueMutation.model_validate_json(mutation.model_copy(update={"quantity": 6}).model_dump_json())
    with pytest.raises(ValidationError):
        DialogueState.model_validate_json(state.model_copy(update={"question": "quantity"}).model_dump_json())


@pytest.mark.parametrize("question", ["increment_missing", "increment_unknown"])
def test_new_increment_choices_use_existing_action_keys(question):
    now = datetime(2026, 10, 8, tzinfo=UTC)
    target = LineRef(id="saved", revision=1) if question == "increment_unknown" else None
    state = DialogueState(user_id=7, chat_id=7, pending_kind="increment", question=question,
        target=target, focus=ProductMention(description="arroz", source_update_id=1, line=target),
        options=("add", "change_quantity"),
        updated_at=now, expires_at=now + DIALOGUE_TTL)
    assert parse_answer("1", state, now=now).selection == 1
    assert parse_answer("añádelo", state, now=now).kind == "add"
    assert parse_answer("cambiar cantidad", state, now=now).kind == "change_quantity"


def test_pending_add_not_visible_and_cancel_discards(tmp_path):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 8, tzinfo=UTC))
    reply = send(repo, "/anadir arroz", clock=clock)
    assert repo.list_lines() == []
    state = repo.dialogue_state(7, 7, now=clock())
    assert (state.pending_kind, state.question) == ("add", "add_quantity")
    assert "arroz" in reply.text
    assert "arroz" not in send(repo, "/lista", clock=clock).text
    send(repo, "cancelar", clock=clock)
    assert repo.list_lines() == []
    assert repo.dialogue_state(7, 7, now=clock()) is None


def test_quantity_commits_once(tmp_path):
    repo = make_repo(tmp_path)
    send(repo, "/anadir arroz")
    reply = send(repo, "2", update_id=20)
    assert [(l.description, l.quantity) for l in repo.list_lines()] == [("arroz", 2)]
    assert send(repo, "2", update_id=20) == reply
    state = repo.dialogue_state(7, 7, now=datetime.now(UTC))
    assert state.pending_kind is None and state.focus.line.id == repo.list_lines()[0].id


def test_pending_survives_list_greeting_restart_not_expiry(tmp_path):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 8, tzinfo=UTC))
    send(repo, "/anadir arroz", clock=clock)
    state = repo.dialogue_state(7, 7, now=clock())
    assert state is not None
    clock.advance(30)
    for text, proposal in [("hola", Intent(action="greet")), ("qué hay en mi lista", Intent(action="list")),
                           ("qué sabes de leche", Intent(action="product_query", lines=[IntentLine(description="leche")]))]:
        decision = reduce_dialogue(IncomingMessage(update_id=40, user_id=7, chat_id=7, text=text),
                                   proposal, state, [], frozenset(), now=clock())
        assert decision.state == state
        if proposal.action == "greet":
            assert decision.reply_kind == "greeting"
        if proposal.action == "product_query":
            assert decision.legacy_intent == proposal
    clock.advance(869)
    repo = Repository(repo.path)
    repo.migrate()
    assert repo.dialogue_state(7, 7, now=clock()) == state
    clock.advance(1)
    send(repo, "2", clock=clock)
    assert repo.list_lines() == []


def test_duplicates_appearing_after_question_need_new_permission(tmp_path):
    repo = make_repo(tmp_path)
    send(repo, "/anadir arroz")
    seed_line(repo, "arroz", 5)
    send(repo, "2")
    assert [l.quantity for l in repo.list_lines()] == [5]
    state = repo.dialogue_state(7, 7, now=datetime.now(UTC))
    assert state.question == "duplicate_choice"
    send(repo, "añadir otra línea")
    assert sorted(l.quantity for l in repo.list_lines()) == [2, 5]


def test_duplicate_permission_is_bound_to_offered_rows(tmp_path):
    repo = make_repo(tmp_path)
    seed_line(repo, "arroz", 5)
    send(repo, "/anadir arroz")
    send(repo, "añadir otra línea")
    state = repo.dialogue_state(7, 7, now=datetime.now(UTC))
    assert state.duplicate_confirmed and state.question == "add_quantity"
    seed_line(repo, "arroz", 7)
    send(repo, "2")
    assert [l.quantity for l in repo.list_lines()] == [5, 7]
    state = repo.dialogue_state(7, 7, now=datetime.now(UTC))
    assert state.question == "duplicate_choice" and not state.duplicate_confirmed
    send(repo, "añadir otra línea")
    assert [l.quantity for l in repo.list_lines()] == [5, 7, 2]


def test_helper_missing_quantity_does_not_renew_permission(tmp_path):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 8, tzinfo=UTC))
    send(repo, "/anadir arroz", clock=clock)
    state = repo.dialogue_state(7, 7, now=clock())
    clock.advance(30)
    result = answer_addition(DialogueAnswer(kind="quantity"), state, [], now=clock())
    assert result.mutation is None and result.state == state


def test_slash_add_pending_but_complete_add_direct(tmp_path):
    repo = make_repo(tmp_path)
    send(repo, "/anadir arroz")
    assert repo.list_lines() == []
    send(repo, "/anadir 2 leche")
    send(repo, "añade 2 café")
    assert sorted((l.description, l.quantity) for l in repo.list_lines()) == [("café", 2), ("leche", 2)]


def test_legacy_unknown_row_remains_saved(tmp_path):
    repo = make_repo(tmp_path)
    old = seed_line(repo, "arroz")
    send(repo, "/anadir arroz")
    assert repo.list_lines() == [old]
    send(repo, "cambiar cantidad")
    send(repo, "2")
    line = repo.list_lines()[0]
    assert (line.id, line.quantity, line.revision) == (old.id, 2, 2)


def test_product_query_preserves_saved_quantity_question(tmp_path):
    repo = make_repo(tmp_path)
    clock = Clock(datetime(2026, 10, 8, tzinfo=UTC))
    seed_line(repo, "arroz")
    send(repo, "/anadir arroz", clock=clock)
    send(repo, "cambiar cantidad", clock=clock)
    state = repo.dialogue_state(7, 7, now=clock())
    assert state.pending_kind is None and state.question == "quantity"
    clock.advance(30)
    proposal = Intent(action="product_query", lines=[IntentLine(description="leche")])
    decision = reduce_dialogue(IncomingMessage(update_id=40, user_id=7, chat_id=7, text="qué sabes de leche"),
                               proposal, state, repo.list_lines(), frozenset(), now=clock())
    assert decision.legacy_intent == proposal
    assert decision.state == state


def test_v8_preserves_rows_and_prepared_v1(tmp_path):
    from pathlib import Path

    from catalog import PRODUCT_RULES
    from tests.test_dialogue_storage import v5_repo

    repo = v5_repo(tmp_path)
    with sqlite3.connect(repo.path) as db:
        for version in (6, 7):
            db.executescript((Path(__file__).parents[1] / f'migrations/{version:03}.sql').read_text())
        db.executemany('INSERT INTO products VALUES (?,?)',
                       [(rule.id, rule.model_dump_json()) for rule in PRODUCT_RULES])
    old = seed_line(repo, "arroz")
    message = IncomingMessage(update_id=30, user_id=7, chat_id=7, text="añade 2 leche")
    repo.ingest_batch([message], 31)
    prepared = repo.prepare_dialogue(30, Intent(action="add", lines=[IntentLine(description="leche", quantity=2)]), "dry_run", now=datetime.now(UTC))
    # Freeze the actual historical v1 contract, not the current factory version.
    from presentation import PresentationSnapshot

    historical = prepared.snapshot.model_dump(mode="json", exclude={"act", "phrases"})
    historical["version"] = 1
    prepared = prepared.model_copy(update={"snapshot": PresentationSnapshot.model_validate_json(
        json.dumps(historical))})
    rows = repo.list_lines()
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE presentation_jobs SET snapshot_json=? WHERE update_id=30",
                   (prepared.snapshot.model_dump_json(),))
        payload = json.loads(db.execute("SELECT state_json FROM dialogue_state").fetchone()[0])
        for key in ("version", "pending_kind", "base_quantity", "additional_quantity", "increment_confirmed"):
            del payload[key]
        db.execute("UPDATE dialogue_state SET state_json=?", (json.dumps(payload),))
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                  if r[0] != "dialogue_state"]
        queries = {t: f"SELECT {'update_id,user_id,chat_id,text,completed,reply_json' if t == 'inbox' else '*'} "
                      f'FROM "{t}" ORDER BY rowid' for t in tables}
        durable = {t: db.execute(query).fetchall() for t, query in queries.items()}
    repo.migrate()
    repo.migrate()
    assert repo.list_lines() == rows and old in rows
    assert repo.dialogue_state(7, 7, now=datetime.now(UTC)) is None
    with sqlite3.connect(repo.path) as db:
        assert {t: db.execute(query).fetchall() for t, query in queries.items()} == durable
    assert repo.prepared_presentation(30) == prepared
    assert repo.apply_dialogue(30, None, "dry_run", now=datetime.now(UTC)) == prepared.snapshot.fallback
    assert repo.list_lines() == rows
    with sqlite3.connect(repo.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 10
        db.execute("PRAGMA user_version=11")
    with pytest.raises(ValueError):
        repo.migrate()
