from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from dialogue import (
    DialogueDecision,
    DialogueMutation,
    DialogueState,
    LineRef,
    ProductMention,
    canonical_name,
    expired,
    parse_answer,
)
from domain import Intent
from tests.dialogue_support import Clock, make_repo, order_count, seed_line, send


@pytest.fixture
def state():
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)
    line = LineRef(id="line-a", revision=1)
    return DialogueState(
        user_id=7, chat_id=7,
        focus=ProductMention(description="arroz integral", source_update_id=1, line=line),
        target=line, updated_at=now, expires_at=now + timedelta(minutes=15),
    )


@pytest.fixture
def duplicate_state(state):
    return state.model_copy(update={
        "question": "duplicate_choice", "options": ("add", "change_quantity"),
    })


@pytest.fixture
def replace_state(state):
    return state.model_copy(update={"question": "confirm_replace"})


def test_expiry_boundary_and_canonical_product_names(state):
    assert expired(state, state.updated_at + timedelta(seconds=899)) is False
    assert expired(state, state.updated_at + timedelta(seconds=900)) is True
    assert canonical_name("  ARRÓZ   integral ") == "arroz integral"
    assert canonical_name("arroz") != canonical_name("arroz integral")
    assert canonical_name("leche 1 litro") != canonical_name("leche 2 litros")


def test_answers_require_one_live_question(duplicate_state, replace_state):
    assert parse_answer("sí", duplicate_state, now=duplicate_state.updated_at) is None
    assert parse_answer("sí", replace_state, now=replace_state.updated_at).kind == "confirm"
    assert parse_answer("añádelo", None, now=replace_state.updated_at) is None
    assert parse_answer("sí", replace_state, now=replace_state.expires_at) is None


@pytest.mark.parametrize("text", ["/comprar", "compra la lista", "2 kg", "0", "-2", "2.5",
                                      "2 litros", "2 piezas", "2 paquetes y compra", "sí compra"])
def test_answer_never_authorizes_purchase_or_unsupported_units(state, text):
    pending = state.model_copy(update={"question": "quantity"})
    assert parse_answer(text, pending, now=state.updated_at) is None


def test_contract_rejects_model_control_fields(state):
    assert Intent(action="mention_product").action == "mention_product"
    with pytest.raises(ValidationError):
        Intent(action="mention_product", duplicate_confirmed=True)
    with pytest.raises(ValidationError):
        DialogueDecision(mutation=DialogueMutation(kind="add", description="arroz", quantity=2),
                         legacy_intent=Intent(action="list"), state=state, reply_kind="added")
    with pytest.raises(ValidationError):
        LineRef(id="a", revision=0)
    with pytest.raises(ValidationError):
        ProductMention(description="arroz", source_update_id=1, duplicate_confirmed=True)
    with pytest.raises(ValidationError):
        DialogueState(**(state.model_dump() | {"updated_at": state.updated_at.replace(tzinfo=None)}))


def test_quantity_and_selection_are_question_specific(state):
    quantity = state.model_copy(update={"question": "quantity"})
    selection = state.model_copy(update={
        "question": "select_line",
        "candidates": (LineRef(id="a", revision=1), LineRef(id="b", revision=2)),
    })
    assert parse_answer("2", quantity, now=state.updated_at).quantity == 2
    assert parse_answer("2", quantity, now=state.updated_at).kind == "quantity"
    assert parse_answer("2", selection, now=state.updated_at).selection == 2
    assert parse_answer("2", selection, now=state.updated_at).kind == "select"
    assert parse_answer("3", selection, now=state.updated_at) is None
    assert parse_answer("2 paquetes", selection, now=state.updated_at) is None
    assert parse_answer("2", state, now=state.updated_at) is None
    assert parse_answer("2", None, now=state.updated_at) is None


@pytest.mark.parametrize("text,question,kind", [
    ("añádelo", "add_or_replace", "add"),
    (" AÑÁDELO   a mi lista ", "add_or_replace", "add"),
    ("añade eso", "add_or_replace", "add"),
    ("añadir otra línea", "duplicate_choice", "add"),
    ("cambiar cantidad", "duplicate_choice", "change_quantity"),
    ("sustitúyelo", "add_or_replace", "replace"),
    ("confirmo", "confirm_replace", "confirm"),
    ("sí", "replace_duplicate", "confirm"),
    ("conserva la cantidad", "replace_quantity", "keep_quantity"),
    ("cancelar", "quantity", "cancel"),
    ("no", "confirm_replace", "cancel"),
])
def test_closed_vocabulary_is_scoped(state, text, question, kind):
    options = (kind,) if question in {"add_or_replace", "duplicate_choice"} else ()
    pending = state.model_copy(update={"question": question, "options": options})
    assert parse_answer(text, pending, now=state.updated_at).kind == kind
    if kind != "cancel":
        assert parse_answer(text, state, now=state.updated_at) is None
        assert parse_answer(text + " por favor", pending, now=state.updated_at) is None


@pytest.mark.parametrize("question,text,unoffered_options", [
    ("add_or_replace", "añádelo", ("replace",)),
    ("add_or_replace", "añádelo a mi lista", ("replace",)),
    ("add_or_replace", "añade eso", ("replace",)),
    ("add_or_replace", "sustitúyelo", ("add",)),
    ("duplicate_choice", "añadir otra línea", ("change_quantity",)),
    ("duplicate_choice", "cambiar cantidad", ("add",)),
])
@pytest.mark.parametrize("empty_options", [False, True])
def test_textual_choice_requires_offered_action(state, question, text,
                                              unoffered_options, empty_options):
    pending = state.model_copy(update={
        "question": question, "options": () if empty_options else unoffered_options,
    })
    assert parse_answer(text, pending, now=state.updated_at) is None


def test_choice_options_are_action_keys_not_display_labels(state):
    pending = state.model_copy(update={
        "question": "duplicate_choice", "options": ("añadir otra línea",),
    })
    assert parse_answer("añadir otra línea", pending, now=state.updated_at) is None


def test_numeric_choice_uses_offered_action_order(state):
    pending = state.model_copy(update={
        "question": "duplicate_choice", "options": ("change_quantity", "add"),
    })
    answer = parse_answer("2", pending, now=state.updated_at)
    assert (answer.kind, answer.selection) == ("select", 2)
    assert parse_answer("3", pending, now=state.updated_at) is None


@pytest.mark.parametrize("unit", ["envases", "paquetes", "botes", "sacos"])
def test_supported_units_and_bare_quantity(state, unit):
    pending = state.model_copy(update={"question": "replace_quantity"})
    answer = parse_answer(f"2 {unit}", pending, now=state.updated_at)
    assert (answer.kind, answer.quantity, answer.unit) == ("quantity", 2, unit)
    assert parse_answer("2", pending, now=state.updated_at).unit is None


def test_cancel_without_context_is_safe_and_remove_id_is_closed(state):
    assert parse_answer("cancelar", None, now=state.updated_at).kind == "cancel"
    assert parse_answer("no", None, now=state.updated_at) is None
    pending = state.model_copy(update={
        "question": "remove_id", "candidates": (state.target,),
    })
    assert parse_answer("line-a", pending, now=state.updated_at).line_id == "line-a"
    assert parse_answer("line-b", pending, now=state.updated_at) is None


def test_helpers_use_real_durable_inbox_and_temporary_repository(tmp_path):
    repo = make_repo(tmp_path)
    line = seed_line(repo, "arroz integral", 2)
    assert (line.description, line.quantity, line.revision) == ("arroz integral", 2, 1)
    reply = send(repo, "/lista", update_id=50)
    assert line.id in reply.text
    assert send(repo, "/lista", update_id=50) == reply
    assert len(repo.list_lines()) == 1
    assert order_count(repo) == 0
    clock = Clock(datetime(2026, 10, 1, 12, tzinfo=UTC))
    clock.advance(900)
    assert clock() == datetime(2026, 10, 1, 12, 15, tzinfo=UTC)


def test_unrepresentable_numeric_answer_fails_closed(state):
    pending = state.model_copy(update={"question": "quantity"})
    assert parse_answer("9" * 5000, pending, now=state.updated_at) is None
    selection = state.model_copy(update={"question": "select_line", "candidates": (state.target,)})
    assert parse_answer("9" * 5000, selection, now=state.updated_at) is None
