import asyncio
import importlib
import json
from datetime import UTC, datetime

import httpx
import pytest

from dialogue_controller import literal_request, reduce_dialogue, validate_model
from domain import IncomingMessage, Intent
from interpreter import parse_command
from ollama_interpreter import OllamaInterpreter


def classify(text):
    return importlib.import_module("dialogue_requests").classify_request(text)


@pytest.mark.parametrize("text", ["hols", "hola", "¡HOLA qué tal!", "buenas", "Buenos días", "qué tal"])
def test_greeting_is_not_list(text):
    assert validate_model(text, Intent(action="list"), []).action == "clarify"
    assert classify(text).action == "greet"


@pytest.mark.parametrize("text", ["lista", "¿qué hay en la lista?", "qué hay en mi lista", "muestra la lista", "muestra mi lista", "dame mi lista"])
def test_whole_list_request_required(text):
    assert classify(text).action == "list"
    assert validate_model(text, Intent(action="list"), []).action == "list"


@pytest.mark.parametrize("text", ['"mi lista"', "no muestra mi lista", "si puedes dame mi lista", "holaqué tal", "mi lista", "dame mi lista y compra", "hola /comprar", "hola, compra la lista"])
def test_non_requests_cannot_authorize_list_or_buy(text):
    assert classify(text) is None
    assert validate_model(text, Intent(action="list"), []).action == "clarify"
    assert validate_model(text, Intent(action="buy"), []).action == "clarify"


@pytest.mark.parametrize("text,action,name", [
    ("Hola, necesito Arroz Integral", "add", "Arroz Integral"),
    ("hola quiero Arroz Hola", "add", "Arroz Hola"),
    ("necesito Arroz Más", "add", "Arroz Más"),
    ("quiero más arroz integral", "increment", "arroz integral"),
    ("AÑADE MÁS Café molido", "increment", "Café molido"),
    ("Hola, quiero más Dodot talla 4", "increment", "Dodot talla 4"),
    ("QUIERO Arroz ÍNTEGRAL por favor", "add", "Arroz ÍNTEGRAL"),
    ("ahora Blemil etapa 2", "mention_product", "Blemil etapa 2"),
])
def test_source_keeps_literal_name_and_modifier(text, action, name):
    request = classify(text)
    assert (request.action, request.description) == (action, name)
    assert literal_request(text) == ((action, name) if action in {"add", "mention_product"} else None)
    assert validate_model(text, Intent(action=action, lines=[{"description": name}]), []).action == action


@pytest.mark.parametrize("text", [
    'quiero más "arroz"', "quiero más arroz si hay oferta", "quiero más arroz y pasta",
    "quiero más 2 arroz", "quiero más arroz no integral", "quiero más https://example.org",
    "quiero más", "quiero más eso", "Arroz Hola", "quiero más arroz cuando haya oferta",
])
def test_unsafe_or_ambiguous_increment_is_not_classified(text):
    assert classify(text) is None


@pytest.mark.parametrize("changes", [
    {"description": "arroz"}, {"description": "arroz integral", "quantity": 2},
    {"description": "arroz integral", "line_id": "chosen"},
    {"description": "arroz integral", "url": "https://example.org"},
])
def test_model_cannot_choose_increment_data(changes):
    proposal = Intent(action="increment", lines=[changes])
    assert validate_model("quiero más arroz integral", proposal, []).action == "clarify"


@pytest.mark.parametrize("text,action,name", [
    ("añade más arroz", "increment", "arroz"),
    ("Hola, necesito Arroz Integral", "add", "Arroz Integral"),
    ("hola", "greet", None), ("dame mi lista", "list", None),
    ("¿qué sabes de Café?", "product_query", "Café"),
])
def test_source_constrained_ollama_schema(text, action, name):
    def respond(request):
        body = json.loads(request.content)
        success = body["format"]["anyOf"][0]["properties"]
        assert success["action"]["enum"] == [action]
        lines = success["lines"]
        if name is None:
            assert lines["maxItems"] == 0
        else:
            assert lines["items"]["properties"]["description"]["enum"] == [name]
            assert lines["items"]["properties"]["quantity"] == {"type": "null"}
        return httpx.Response(200, json={"message": {"role": "assistant", "content": json.dumps({
            "action": action, "lines": [] if name is None else [{"description": name, "quantity": None}],
        })}})

    model = OllamaInterpreter(transport=httpx.MockTransport(respond))
    result = asyncio.run(model.parse_with_dialogue(text, [], [], None))
    assert result.action == action


@pytest.mark.parametrize("text,output", [
    ("añade más arroz", {"action": "add", "lines": [{"description": "más arroz"}]}),
    ("quiero más Arroz", {"action": "increment", "lines": [{"description": "arroz"}]}),
    ("hola", {"action": "list"}), ("holaqué tal", {"action": "list"}),
])
def test_dialogue_ollama_rejects_incompatible_proposal(text, output):
    model = OllamaInterpreter(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, json={"message": {"role": "assistant", "content": json.dumps(output)}},
    )))
    assert asyncio.run(model.parse_with_dialogue(text, [], [], None)).action == "clarify"


def test_increment_never_adds_literal_more_at_reducer_boundary():
    text = "añade más arroz"
    # The legacy parser deliberately stays compatible; consumers must guard it.
    assert parse_command(text, []).lines[0].description == "más arroz"
    message = IncomingMessage(update_id=1, user_id=1, chat_id=1, text=text)
    decision = reduce_dialogue(message, Intent(action="add", lines=[{"description": "más arroz"}]),
                               None, [], frozenset(), now=datetime(2026, 10, 8, tzinfo=UTC))
    assert decision.mutation is None
    assert decision.legacy_intent is None
    assert decision.reply_kind == "clarify"


@pytest.mark.parametrize("method", ["parse", "parse_with_context"])
def test_legacy_ollama_increment_cannot_return_literal_add(method):
    model = OllamaInterpreter(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, json={"message": {"role": "assistant", "content": json.dumps({
            "action": "add", "lines": [{"description": "más arroz"}],
        })}},
    )))
    args = ("añade más arroz", []) if method == "parse" else ("añade más arroz", [], [])
    assert asyncio.run(getattr(model, method)(*args)).action == "clarify"


@pytest.mark.parametrize("text,name,quantity", [
    ("añade 2 arroz", "arroz", 2), ("/anadir más arroz", "más arroz", None),
])
def test_explicit_additions_keep_legacy_priority(text, name, quantity):
    message = IncomingMessage(update_id=1, user_id=1, chat_id=1, text=text)
    decision = reduce_dialogue(message, None, None, [], frozenset(), now=datetime(2026, 10, 8, tzinfo=UTC))
    if quantity is None:
        assert decision.mutation is None
        assert (decision.state.focus.description, decision.state.question) == (name, "add_quantity")
    else:
        assert decision.mutation.kind == "add"
        assert (decision.mutation.description, decision.mutation.quantity) == (name, quantity)
