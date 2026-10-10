import sqlite3
from datetime import UTC, datetime

import pytest

from domain import IncomingMessage, Intent, IntentLine
from tests.dialogue_support import Clock, make_repo, order_count, seed_line, send
from tests.fakes import FakeInterpreter


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


@pytest.fixture
def clock():
    return Clock(datetime(2026, 10, 1, tzinfo=UTC))


def propose(name, action="mention_product"):
    return FakeInterpreter(Intent(action=action, lines=[IntentLine(description=name)]))


def start(repo, clock, quantity=2, destination="arroz integral"):
    if quantity is None:
        line = seed_line(repo, "arroz")
        send(repo, "/comprar", clock=clock)
        assert repo.dialogue_state(7, 7, now=clock()).target.id == line.id
    else:
        send(repo, f"/anadir {quantity} arroz", clock=clock)
    original = repo.list_lines()[0]
    send(repo, "ahora " + destination, propose(destination), clock=clock)
    return original


@pytest.mark.parametrize("answer,quantity", [("conserva la cantidad", 2), ("3 botes", 3)])
def test_replace_requires_origin_destination_confirmation_and_quantity(repo, clock, answer, quantity):
    original = start(repo, clock)
    reply = send(repo, "sustitúyelo", clock=clock)
    assert "arroz" in reply.text and "arroz integral" in reply.text
    assert repo.list_lines() == [original]
    reply = send(repo, "sí", clock=clock)
    assert "cantidad" in reply.text and "2" in reply.text
    assert repo.list_lines() == [original]
    reply = send(repo, answer, clock=clock)
    changed = repo.list_lines()[0]
    assert (changed.id, changed.description, changed.quantity, changed.revision) == (
        original.id, "arroz integral", quantity, original.revision + 1,
    )
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT source_update_id FROM list_lines WHERE id=?", (changed.id,)).fetchone()[0] == 1
    assert "arroz integral" in reply.text and str(quantity) in reply.text
    state = repo.dialogue_state(7, 7, now=clock())
    assert state.focus.line.id == changed.id and state.focus.line.revision == changed.revision
    assert state.question is None and state.target is None
    assert order_count(repo) == 0


def test_replace_missing_quantity_does_not_delete_origin(repo, clock):
    original = start(repo, clock, None)
    send(repo, "sustitúyelo", clock=clock)
    send(repo, "sí", clock=clock)
    send(repo, "conserva la cantidad", clock=clock)
    send(repo, "0", clock=clock)
    assert repo.list_lines() == [original]
    send(repo, "3", clock=clock)
    assert repo.list_lines()[0].quantity == 3
    assert repo.list_lines()[0].description == "arroz integral"


@pytest.mark.parametrize("finish", ["no", "cancelar", "sí"])
def test_duplicate_destination_requires_separate_lines_confirmation(repo, clock, finish):
    original = start(repo, clock)
    duplicate = seed_line(repo, "ARROZ  integral", 4)
    send(repo, "sustitúyelo", clock=clock)
    send(repo, "sí", clock=clock)
    reply = send(repo, "3", clock=clock)
    assert "separadas" in reply.text
    assert repo.list_lines() == [original, duplicate]
    send(repo, finish, clock=clock)
    changed, preserved = repo.list_lines()
    assert preserved == duplicate
    if finish == "sí":
        assert (changed.id, changed.description, changed.quantity) == (original.id, "arroz integral", 3)
    else:
        assert changed == original


def synthetic_order(repo):
    update = repo.telegram_offset()
    repo.ingest_batch([IncomingMessage(update_id=update, user_id=7, chat_id=7, text="test order")], update + 1)
    return repo.apply_intent(update, Intent(action="buy"), "dry_run").order_id


@pytest.mark.parametrize("change", ["stale", "missing", "reserved"])
@pytest.mark.parametrize("stage", ["confirm_replace", "replace_quantity"])
def test_replacement_rejects_stale_missing_or_reserved_origin(repo, clock, change, stage):
    original = start(repo, clock)
    send(repo, "sustitúyelo", clock=clock)
    if stage == "replace_quantity":
        send(repo, "sí", clock=clock)
    with sqlite3.connect(repo.path) as db:
        if change == "stale":
            db.execute("UPDATE list_lines SET revision=revision+1 WHERE id=?", (original.id,))
        elif change == "missing":
            db.execute("DELETE FROM list_lines WHERE id=?", (original.id,))
    if change == "reserved":
        assert synthetic_order(repo)
    before = repo.list_lines()
    reply = send(repo, "sí" if stage == "confirm_replace" else "3", clock=clock)
    assert repo.list_lines() == before
    assert "cambiado" in reply.text or "reservada" in reply.text
    if change == "reserved":
        with sqlite3.connect(repo.path) as db:
            assert db.execute("SELECT line_id FROM reservations").fetchall() == [(original.id,)]


@pytest.mark.parametrize("name", ["Blemil etapa 2", "pienso pollo"])
def test_restricted_replacement_preserves_full_description(repo, clock, name):
    original = start(repo, clock, destination=name)
    send(repo, "sustitúyelo", clock=clock)
    send(repo, "sí", clock=clock)
    send(repo, "conserva la cantidad", clock=clock)
    changed = repo.list_lines()[0]
    assert changed.id == original.id and changed.description == name
    assert changed.product_id is None


def test_replace_outbox_failure_rolls_back_and_retry_changes_once(repo, clock):
    original = start(repo, clock)
    send(repo, "sustitúyelo", clock=clock)
    send(repo, "sí", clock=clock)
    before = repo.dialogue_state(7, 7, now=clock())
    update = repo.telegram_offset()
    message = IncomingMessage(update_id=update, user_id=7, chat_id=7, text="3")
    repo.ingest_batch([message], update + 1)
    with sqlite3.connect(repo.path) as db:
        inbox = db.execute("SELECT * FROM inbox WHERE update_id=?", (update,)).fetchone()
        db.executescript("CREATE TRIGGER reject_replace BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'injected'); END;")
    clock.advance(30)
    with pytest.raises(sqlite3.IntegrityError):
        repo.apply_dialogue(update, None, "dry_run", now=clock())
    assert repo.list_lines() == [original]
    assert repo.dialogue_state(7, 7, now=clock()) == before
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT * FROM inbox WHERE update_id=?", (update,)).fetchone() == inbox
        assert db.execute("SELECT count(*) FROM outbox WHERE update_id=?", (update,)).fetchone()[0] == 0
        db.execute("DROP TRIGGER reject_replace")
    reply = repo.apply_dialogue(update, None, "dry_run", now=clock())
    after = repo.dialogue_state(7, 7, now=clock())
    clock.advance(30)
    assert repo.apply_dialogue(update, Intent(action="buy"), "dry_run", now=clock()) == reply
    assert repo.dialogue_state(7, 7, now=clock()) == after
    assert repo.list_lines()[0].revision == original.revision + 1


def test_prior_order_snapshot_immutable_after_allowed_replace(repo, clock):
    original = start(repo, clock)
    oid = synthetic_order(repo)
    assert oid
    with sqlite3.connect(repo.path) as db:
        snapshot = db.execute("SELECT * FROM order_lines WHERE order_id=?", (oid,)).fetchall()
        # Simulate a prior order no longer owning the line; no checkout execution.
        db.execute("DELETE FROM reservations WHERE order_id=?", (oid,))
    send(repo, "sustitúyelo", clock=clock)
    send(repo, "sí", clock=clock)
    send(repo, "3", clock=clock)
    assert repo.list_lines()[0].revision == original.revision + 1
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT * FROM order_lines WHERE order_id=?", (oid,)).fetchall() == snapshot


@pytest.mark.parametrize("action", ["remove", "set_quantity", "buy"])
def test_model_replace_or_set_quantity_cannot_confirm_pending_proposal(repo, clock, action):
    original = start(repo, clock)
    send(repo, "sustitúyelo", clock=clock)
    before = repo.dialogue_state(7, 7, now=clock())
    update = repo.telegram_offset()
    repo.ingest_batch([IncomingMessage(update_id=update, user_id=7, chat_id=7, text="sí si hay oferta")], update + 1)
    repo.apply_dialogue(update, Intent(action=action, lines=[IntentLine(line_id="fabricated", quantity=9)]), "dry_run", now=clock())
    assert repo.list_lines() == [original]
    assert repo.dialogue_state(7, 7, now=clock()) == before
    assert order_count(repo) == 0


@pytest.mark.parametrize("stage", ["add_or_replace", "confirm_replace", "replace_quantity", "replace_duplicate"])
def test_cancel_at_every_replace_step_preserves_original(repo, clock, stage):
    original = start(repo, clock)
    if stage == "replace_duplicate":
        seed_line(repo, "arroz integral", 4)
    before = repo.list_lines()
    if stage != "add_or_replace":
        send(repo, "sustitúyelo", clock=clock)
    if stage in {"replace_quantity", "replace_duplicate"}:
        send(repo, "sí", clock=clock)
    if stage == "replace_duplicate":
        send(repo, "3", clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).question == stage
    send(repo, "cancelar", clock=clock)
    send(repo, "sí", clock=clock)
    send(repo, "3", clock=clock)
    assert repo.list_lines() == before and repo.list_lines()[0] == original


def test_duplicate_focus_then_replacement_updates_same_existing_id(repo, clock):
    seed_line(repo, "arroz", 2)
    send(repo, "necesito arroz", propose("arroz", "add"), clock=clock)
    send(repo, "cambiar cantidad", clock=clock)
    send(repo, "2", clock=clock)
    original = repo.list_lines()[0]
    send(repo, "ahora arroz integral", propose("arroz integral"), clock=clock)
    send(repo, "2", clock=clock)  # offered replace action, not a quantity
    send(repo, "2", clock=clock)  # cannot confirm with a quantity
    assert repo.list_lines() == [original]
    send(repo, "sí", clock=clock)
    send(repo, "conserva la cantidad", clock=clock)
    assert repo.list_lines()[0].id == original.id
    assert repo.list_lines()[0].revision == original.revision + 1


def test_new_duplicate_requires_a_new_separate_lines_confirmation(repo, clock):
    original = start(repo, clock)
    first = seed_line(repo, "arroz integral", 4)
    send(repo, "sustitúyelo", clock=clock)
    send(repo, "sí", clock=clock)
    send(repo, "3", clock=clock)
    second = seed_line(repo, "arroz integral", 5)
    reply = send(repo, "sí", clock=clock)
    assert "separadas" in reply.text
    assert repo.list_lines() == [original, first, second]
    assert not repo.dialogue_state(7, 7, now=clock()).duplicate_confirmed
    send(repo, "sí", clock=clock)
    assert repo.list_lines()[0].description == "arroz integral"
    assert repo.list_lines()[1:] == [first, second]


def test_changed_duplicate_invalidates_confirmation_without_touching_origin(repo, clock):
    original = start(repo, clock)
    duplicate = seed_line(repo, "arroz integral", 4)
    send(repo, "sustitúyelo", clock=clock)
    send(repo, "sí", clock=clock)
    send(repo, "3", clock=clock)
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE list_lines SET revision=revision+1 WHERE id=?", (duplicate.id,))
    reply = send(repo, "sí", clock=clock)
    assert "cambiado" in reply.text
    assert repo.list_lines()[0] == original


@pytest.mark.parametrize("seconds,replaced", [(899, True), (900, False)])
def test_pending_replacement_restart_and_exact_expiry(repo, clock, seconds, replaced):
    from storage import Repository

    original = start(repo, clock)
    send(repo, "sustitúyelo", clock=clock)
    send(repo, "sí", clock=clock)
    clock.advance(seconds)
    send(Repository(repo.path), "3", clock=clock)
    assert (repo.list_lines()[0].description == "arroz integral") is replaced
    if not replaced:
        assert repo.list_lines() == [original]


def test_diaper_replacement_requires_explicit_packages_even_when_keeping(repo, clock):
    original = start(repo, clock, destination="Dodot talla 4")
    send(repo, "sustitúyelo", clock=clock)
    send(repo, "sí", clock=clock)
    send(repo, "conserva la cantidad", clock=clock)
    send(repo, "3", clock=clock)
    assert repo.list_lines() == [original]
    send(repo, "3 paquetes", clock=clock)
    assert repo.list_lines()[0].description == "Dodot talla 4"
    assert repo.list_lines()[0].quantity == 3


def test_zero_affected_replacement_rolls_back_pending_confirmation(repo, clock):
    original = start(repo, clock)
    send(repo, "sustitúyelo", clock=clock)
    send(repo, "sí", clock=clock)
    before = repo.dialogue_state(7, 7, now=clock())
    with sqlite3.connect(repo.path) as db:
        db.executescript("CREATE TRIGGER ignore_replace BEFORE UPDATE ON list_lines BEGIN SELECT RAISE(IGNORE); END;")
    with pytest.raises(ValueError, match="exactly one"):
        send(repo, "3", clock=clock)
    assert repo.list_lines() == [original]
    assert repo.dialogue_state(7, 7, now=clock()) == before


@pytest.mark.parametrize("interrupt", ["¿qué sabes de pasta?", "/lista"])
def test_product_query_and_list_preserve_pending_replacement(repo, clock, interrupt):
    start(repo, clock)
    send(repo, "sustitúyelo", clock=clock)
    send(repo, "sí", clock=clock)
    before = repo.dialogue_state(7, 7, now=clock())
    clock.advance(30)
    send(repo, interrupt, propose("pasta", "product_query"), clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()) == before
    send(repo, "3", clock=clock)
    assert repo.list_lines()[0].description == "arroz integral"


def test_reserved_origin_does_not_block_offered_numeric_add_alternative(repo, clock):
    original = start(repo, clock)
    assert synthetic_order(repo)
    send(repo, "1", clock=clock)
    assert repo.list_lines()[0] == original
    assert len(repo.list_lines()) == 1
    send(repo, "2", clock=clock)
    assert [l.description for l in repo.list_lines()] == ["arroz", "arroz integral"]
