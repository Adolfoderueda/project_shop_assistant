import json
import sqlite3
from datetime import UTC, datetime

import httpx
import pytest

from domain import Intent, IntentLine
from ollama_interpreter import OllamaInterpreter
from tests.dialogue_support import Clock, make_repo, order_count, seed_line, send
from tests.fakes import FakeInterpreter


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


@pytest.fixture
def clock():
    return Clock(datetime(2026, 10, 1, tzinfo=UTC))


def proposal(name, action="add", **kwargs):
    return FakeInterpreter(Intent(action=action, lines=[IntentLine(description=name, **kwargs)]))


def test_capture_flow_remembers_product_without_literal_pronouns(repo, clock):
    send(repo, "necesito arroz por favor", proposal("arroz"), clock=clock)
    send(repo, "2", clock=clock)
    reply = send(repo, "ahora arroz integral", proposal("arroz integral", "mention_product"), clock=clock)
    assert "añadir" in reply.text.lower() and "sustituir" in reply.text.lower()
    assert len(repo.list_lines()) == 1
    send(repo, "añádelo a mi lista", clock=clock)
    send(repo, "2 paquetes", clock=clock)
    assert [(l.description, l.quantity) for l in repo.list_lines()] == [("arroz", 2), ("arroz integral", 2)]
    assert order_count(repo) == 0


def test_new_line_not_old_missing_line_receives_quantity(repo, clock):
    seed_line(repo, "arroz")
    send(repo, "necesito pasta", proposal("pasta"), clock=clock)
    send(repo, "2", clock=clock)
    assert [l.quantity for l in repo.list_lines()] == [None, 2]


@pytest.mark.parametrize("text", ["necesito arroz", "/anadir arroz"])
def test_duplicate_requires_choice_for_natural_and_slash_add(repo, clock, text):
    seed_line(repo, "arroz", 1)
    send(repo, text, proposal("arroz"), clock=clock)
    send(repo, "sí", clock=clock)
    assert [l.quantity for l in repo.list_lines()] == [1]
    send(repo, "cambiar cantidad", clock=clock)
    send(repo, "2", clock=clock)
    assert [l.quantity for l in repo.list_lines()] == [2]
    send(repo, text, proposal("arroz"), clock=clock)
    send(repo, "añadir otra línea", clock=clock)
    assert len(repo.list_lines()) == 1
    send(repo, "3", clock=clock)
    assert len(repo.list_lines()) == 2


@pytest.mark.parametrize("names", [("Dodot talla 3", "Dodot talla 4"), ("pienso", "pienso pollo")])
def test_same_product_id_different_qualifier_not_duplicate(repo, clock, names):
    seed_line(repo, names[0], 1)
    send(repo, "necesito " + names[1], proposal(names[1]), clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).question == "add_quantity"
    send(repo, "2 paquetes", clock=clock)
    assert [l.description for l in repo.list_lines()] == list(names)


def test_contextual_alias_never_adds_pronoun(repo, clock):
    send(repo, "añade eso", clock=clock)
    assert repo.list_lines() == []
    send(repo, "ahora pasta", proposal("pasta", "mention_product"), clock=clock)
    send(repo, "añade eso", clock=clock)
    assert repo.list_lines() == []
    send(repo, "2", clock=clock)
    assert [l.description for l in repo.list_lines()] == ["pasta"]


@pytest.mark.parametrize("text,name,kwargs", [
    ("ahora arroz integral", "arroz", {}),
    ("ahora arroz", "arroz", {"quantity": 2}),
    ("ahora arroz", "arroz", {"line_id": "fake"}),
    ("ahora arroz", "arroz", {"url": "https://example.com"}),
    ("ahora arroz si hay oferta", "arroz si hay oferta", {}),
    ('ahora "arroz"', '"arroz"', {}),
    ("¿ahora arroz?", "arroz", {}),
])
def test_model_cannot_invent_focus_or_write_from_question(repo, clock, text, name, kwargs):
    send(repo, text, proposal(name, "mention_product", **kwargs), clock=clock)
    send(repo, "añade eso", clock=clock)
    assert repo.list_lines() == []
    assert repo.dialogue_state(7, 7, now=clock()) is None


@pytest.mark.parametrize("seconds,quantity", [(899, 2), (900, None)])
def test_expiry_and_restart(repo, clock, seconds, quantity):
    send(repo, "necesito arroz", proposal("arroz"), clock=clock)
    clock.advance(seconds)
    from storage import Repository
    send(Repository(repo.path), "2", clock=clock)
    assert [l.quantity for l in repo.list_lines()] == ([] if quantity is None else [quantity])


@pytest.mark.parametrize("interrupt", ["cancelar", "¿qué sabes de pasta?"])
def test_cancel_discards_but_product_query_preserves_pending_quantity(repo, clock, interrupt):
    send(repo, "necesito arroz", proposal("arroz"), clock=clock)
    send(repo, interrupt, proposal("pasta", "product_query"), clock=clock)
    send(repo, "2", clock=clock)
    assert [(l.description, l.quantity) for l in repo.list_lines()] == (
        [] if interrupt == "cancelar" else [("arroz", 2)])


def test_options_and_quantity_numbers_cannot_cross(repo, clock):
    seed_line(repo, "arroz", 1)
    send(repo, "/anadir arroz", clock=clock)
    send(repo, "1", clock=clock)
    assert repo.list_lines()[0].quantity == 1
    send(repo, "2", clock=clock)
    assert repo.list_lines()[0].quantity == 2


def test_natural_replies_hide_ids_but_slash_list_keeps_them(repo, clock):
    added = send(repo, "necesito arroz", proposal("arroz"), clock=clock)
    updated = send(repo, "2 paquetes", clock=clock)
    line = repo.list_lines()[0]
    natural = send(repo, "lista", clock=clock)
    assert all(line.id not in r.text for r in (added, updated, natural))
    assert "2 paquetes" in updated.text
    assert line.id in send(repo, "/lista", clock=clock).text


def test_diapers_still_need_explicit_packs(repo, clock):
    send(repo, "necesito pañales", proposal("pañales"), clock=clock)
    send(repo, "2", clock=clock)
    assert repo.list_lines() == []
    send(repo, "2 paquetes", clock=clock)
    assert repo.list_lines()[0].quantity == 2


@pytest.mark.parametrize("name", ["Dodot talla 4", "Blemil etapa 2"])
def test_numeric_product_qualifier_is_preserved_not_quantity(repo, clock, name):
    send(repo, "necesito " + name, proposal(name), clock=clock)
    assert repo.list_lines() == []
    state = repo.dialogue_state(7, 7, now=clock())
    assert (state.focus.description, state.proposal_quantity) == (name, None)
    send(repo, "2 paquetes", clock=clock)
    line = repo.list_lines()[0]
    assert (line.description, line.quantity, line.product_id) == (name, 2, None)


def test_replay_does_not_renew_state(repo, clock):
    send(repo, "necesito arroz", proposal("arroz"), clock=clock, update_id=1)
    before = repo.dialogue_state(7, 7, now=clock())
    clock.advance(30)
    send(repo, "necesito arroz", proposal("arroz"), clock=clock, update_id=1)
    assert repo.dialogue_state(7, 7, now=clock()) == before


def test_list_and_invalid_answer_do_not_renew_question(repo, clock):
    send(repo, "necesito arroz", proposal("arroz"), clock=clock)
    before = repo.dialogue_state(7, 7, now=clock())
    clock.advance(100)
    send(repo, "lista", clock=clock)
    send(repo, "no entiendo", clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()) == before


def test_stale_candidates_cannot_retarget_selection(repo, clock):
    a = seed_line(repo, "arroz", 1)
    seed_line(repo, "arroz", 3)
    send(repo, "/anadir arroz", clock=clock)
    send(repo, "cambiar cantidad", clock=clock)
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE list_lines SET revision=revision+1 WHERE id=?", (a.id,))
    reply = send(repo, "2", clock=clock)
    send(repo, "9", clock=clock)
    assert [l.quantity for l in repo.list_lines()] == [1, 3]
    assert "cambiado" in reply.text


def test_multiple_candidates_selection_updates_only_offered_line(repo, clock):
    seed_line(repo, "arroz", 1)
    seed_line(repo, "arroz", 3)
    send(repo, "/anadir arroz", clock=clock)
    send(repo, "cambiar cantidad", clock=clock)
    send(repo, "2", clock=clock)
    assert [l.quantity for l in repo.list_lines()] == [1, 3]
    send(repo, "4", clock=clock)
    assert [l.quantity for l in repo.list_lines()] == [1, 4]


def test_confirm_replace_is_offered_but_never_executed_in_task3(repo, clock):
    send(repo, "necesito arroz", proposal("arroz"), clock=clock)
    send(repo, "2", clock=clock)
    before = repo.list_lines()
    send(repo, "ahora pasta", proposal("pasta", "mention_product"), clock=clock)
    reply = send(repo, "sustitúyelo", clock=clock)
    assert "arroz" in reply.text and "pasta" in reply.text and "Confirmas" in reply.text
    send(repo, "sí", clock=clock)
    assert repo.list_lines() == before


def test_model_offline_does_not_block_ambiguous_closed_answers(repo, clock):
    class Offline:
        calls = 0

        async def parse(self, text, lines):
            self.calls += 1
            raise AssertionError("Closed answers must never invoke the model")

    seed_line(repo, "arroz", 1)
    send(repo, "/anadir arroz", clock=clock)
    offline = Offline()
    reply = send(repo, "sí", offline, clock=clock)
    assert offline.calls == 0
    assert "cambiar cantidad" in reply.text.lower()
    assert [l.quantity for l in repo.list_lines()] == [1]


def test_new_proposal_replaces_stale_question(repo, clock):
    send(repo, "necesito arroz", proposal("arroz"), clock=clock)
    send(repo, "2", clock=clock)
    line = repo.list_lines()[0]
    with sqlite3.connect(repo.path) as db:
        db.execute("DELETE FROM list_lines WHERE id=?", (line.id,))
    send(repo, "necesito pasta", proposal("pasta"), clock=clock)
    send(repo, "2", clock=clock)
    assert [(l.description, l.quantity) for l in repo.list_lines()] == [("pasta", 2)]


def test_add_quantity_label_is_backed_by_explicit_command(repo, clock):
    reply = send(repo, "/anadir 2 paquetes de arroz", clock=clock)
    assert "2 paquetes" in reply.text


def test_dialogue_write_and_state_roll_back_when_outbox_fails(repo, clock):
    send(repo, "necesito arroz", proposal("arroz"), clock=clock)
    before = repo.dialogue_state(7, 7, now=clock())
    with sqlite3.connect(repo.path) as db:
        db.executescript("CREATE TRIGGER reject_notice BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'injected'); END;")
    clock.advance(30)
    with pytest.raises(sqlite3.IntegrityError):
        send(repo, "2", clock=clock)
    assert repo.list_lines() == []
    assert repo.dialogue_state(7, 7, now=clock()) == before


@pytest.mark.parametrize("name,omitted", [("Dodot talla 4", "Dodot"), ("Blemil etapa 2", "Blemil")])
def test_numeric_qualifier_cannot_be_omitted(repo, clock, name, omitted):
    send(repo, "necesito " + name, proposal(omitted), clock=clock)
    assert repo.list_lines() == []
    assert repo.dialogue_state(7, 7, now=clock()) is None


def test_slash_quantity_rebinds_focus_to_actual_revision(repo, clock):
    a = seed_line(repo, "arroz", 1)
    reply = send(repo, f"/cantidad {a.id} 3", clock=clock)
    assert "arroz" in reply.text and "3 envases" in reply.text
    state = repo.dialogue_state(7, 7, now=clock())
    assert state.focus.line.id == a.id and state.focus.line.revision == 2
    send(repo, "ahora pasta", proposal("pasta", "mention_product"), clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).target.id == a.id


def test_repository_reparses_slash_and_rejects_model_destructive_authority(repo, clock):
    from domain import IncomingMessage
    for number, text in enumerate(["necesito arroz", "/anadir pasta"], 1):
        message = IncomingMessage(update_id=number, user_id=7, chat_id=7, text=text)
        repo.ingest_batch([message], number + 1)
        repo.apply_dialogue(number, Intent(action="buy"), "dry_run", now=clock())
    assert repo.list_lines() == []
    assert repo.dialogue_state(7, 7, now=clock()).focus.description == "pasta"
    assert order_count(repo) == 0


def test_optional_dialogue_route_receives_current_question(repo, clock):
    class Contextual:
        async def parse_with_dialogue(self, text, lines, products, state):
            assert state.focus.description == "arroz" and state.question == "add_quantity"
            return Intent(action="mention_product", lines=[IntentLine(description="pasta")])

    send(repo, "necesito arroz", proposal("arroz"), clock=clock)
    reply = send(repo, "ahora pasta", Contextual(), clock=clock)
    assert "añadir pasta" in reply.text
    assert len(repo.list_lines()) == 0


def test_repository_replay_ignores_new_invalid_proposal(repo, clock):
    original = send(repo, "/anadir arroz", clock=clock, update_id=1)
    malformed = Intent(action="add").model_copy(update={"lines": "invalid"})
    assert repo.apply_dialogue(1, malformed, "dry_run", now=clock()) == original
    assert len(repo.list_lines()) == 0


def test_pending_compatibility_does_not_return_stale_line(repo):
    seed_line(repo, "arroz")
    send(repo, "/comprar")
    assert repo.pending_clarification(7) is not None
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE list_lines SET revision=revision+1")
    assert repo.pending_clarification(7) is None


def test_offered_numeric_actions_name_the_origin_and_saved_duplicate_total(repo, clock):
    duplicate = seed_line(repo, "arroz", 3)
    reply = send(repo, "/anadir arroz", clock=clock)
    assert "3 envases" in reply.text
    send(repo, f"/cantidad {duplicate.id} 2", clock=clock)
    reply = send(repo, "ahora pasta", proposal("pasta", "mention_product"), clock=clock)
    assert "1:" in reply.text and "2:" in reply.text and "arroz" in reply.text
    assert duplicate.id not in reply.text


def local_model(content):
    def respond(request):
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    return OllamaInterpreter(transport=httpx.MockTransport(respond))


def test_mention_product_is_proposal_not_mutation(repo, clock):
    send(repo, "necesito arroz", proposal("arroz"), clock=clock)
    send(repo, "2", clock=clock)
    before = repo.list_lines()
    reply = send(repo, "ahora Dodot talla 4", local_model(
        '{"action":"mention_product","lines":[{"description":"Dodot talla 4"}]}',
    ), clock=clock)
    assert repo.list_lines() == before
    assert "añadir Dodot talla 4" in reply.text
    assert repo.dialogue_state(7, 7, now=clock()).focus.description == "Dodot talla 4"
    send(repo, "añádelo", clock=clock)
    assert repo.list_lines() == before
    send(repo, "2 paquetes", clock=clock)
    assert [line.description for line in repo.list_lines()] == ["arroz", "Dodot talla 4"]
    assert repo.list_lines()[1].quantity == 2
    assert order_count(repo) == 0


def test_answers_and_slash_commands_skip_ollama(repo, clock):
    def unavailable(request):
        pytest.fail("Closed answers and slash commands must not contact Ollama")

    model = OllamaInterpreter(transport=httpx.MockTransport(unavailable))
    send(repo, "/anadir arroz", model, clock=clock)
    send(repo, "2", model, clock=clock)
    assert repo.list_lines()[0].quantity == 2
    send(repo, "/lista", model, clock=clock)
    send(repo, "ahora pasta", proposal("pasta", "mention_product"), clock=clock)
    send(repo, "2", model, clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).question == "confirm_replace"
    send(repo, "sí", model, clock=clock)
    assert repo.dialogue_state(7, 7, now=clock()).question == "replace_quantity"
    send(repo, "cancelar", model, clock=clock)
    seed_line(repo, "arroz", 3)
    send(repo, "/anadir arroz", model, clock=clock)
    send(repo, "cambiar cantidad", model, clock=clock)
    send(repo, "2", model, clock=clock)
    send(repo, "4", model, clock=clock)
    assert [line.quantity for line in repo.list_lines()] == [2, 4]


@pytest.mark.parametrize("action", ["set_quantity", "remove", "buy"])
def test_model_destructive_action_with_live_focus_is_rejected(repo, clock, action):
    send(repo, "necesito arroz", proposal("arroz"), clock=clock)
    send(repo, "2", clock=clock)
    before = repo.list_lines()
    state = repo.dialogue_state(7, 7, now=clock())
    model = local_model(json.dumps({"action": action, "lines": [{
        "description": "pasta", "quantity": 8, "line_id": before[0].id,
    }]}))
    send(repo, "ahora pasta", model, clock=clock)
    assert repo.list_lines() == before
    assert repo.dialogue_state(7, 7, now=clock()) == state
    assert order_count(repo) == 0


@pytest.mark.parametrize("failure", ["timeout", "invalid_json", "redirect"])
def test_timeout_invalid_json_and_redirect_preserve_dialogue(repo, clock, failure):
    send(repo, "necesito arroz", proposal("arroz"), clock=clock)
    before = repo.list_lines()
    state = repo.dialogue_state(7, 7, now=clock())
    backlog = repo.product_requests()
    requests = []

    def fail(request):
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private provider error", request=request)
        if failure == "redirect":
            return httpx.Response(302, headers={"location": "https://evil.example/collect"})
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "not JSON"}})

    clock.advance(30)
    reply = send(repo, "ahora pasta", OllamaInterpreter(transport=httpx.MockTransport(fail)), clock=clock)
    assert len(requests) == 1
    assert str(requests[0].url) == "http://127.0.0.1:11434/api/chat"
    assert "private provider error" not in reply.text
    assert repo.list_lines() == before
    assert repo.dialogue_state(7, 7, now=clock()) == state
    assert repo.product_requests() == backlog
    assert order_count(repo) == 0


def test_truncated_context_cannot_grant_confirmation(repo, clock):
    long_name = "arroz " + "integral " * 22 + "marca A"
    for _ in range(7):
        seed_line(repo, long_name, 2)
    send(repo, "/anadir " + long_name, clock=clock)
    send(repo, "cambiar cantidad", clock=clock)
    before = repo.list_lines()
    state = repo.dialogue_state(7, 7, now=clock())
    assert state.question == "select_line" and len(state.candidates) == 7
    contexts = []

    def adversarial(request):
        contexts.append(json.loads(json.loads(request.content)["messages"][1]["content"]))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": json.dumps({
            "action": "set_quantity", "lines": [{"line_id": before[0].id, "quantity": 9}],
        })}})

    reply = send(repo, "esa línea", OllamaInterpreter(transport=httpx.MockTransport(adversarial)), clock=clock)
    assert len(contexts[0]["dialogue"]["candidates"]) == 5
    assert all(len(name) == 160 for name in contexts[0]["dialogue"]["candidates"])
    assert repo.list_lines() == before
    assert repo.dialogue_state(7, 7, now=clock()) == state
    assert "selecciona" in reply.text.lower()
    send(repo, "sí", clock=clock)
    assert repo.list_lines() == before
    # The controller, unlike the model payload, still has all seven offered rows.
    send(repo, "7", clock=clock)
    send(repo, "3", clock=clock)
    assert [line.quantity for line in repo.list_lines()] == [2, 2, 2, 2, 2, 2, 3]
