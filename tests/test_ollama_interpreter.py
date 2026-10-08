import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from dialogue import DialogueState, LineRef, ProductMention
from domain import Intent, ListLine
from ollama_interpreter import OllamaInterpreter
from product_memory import ObservedProduct


def run(text, response, *, lines=None, products=None, contextual=False):
    requests = []

    async def transport(request):
        requests.append(request)
        return response(request) if callable(response) else response

    interpreter = OllamaInterpreter(transport=httpx.MockTransport(transport))
    result = asyncio.run(
        interpreter.parse_with_context(text, lines or [], products or [])
        if contextual else interpreter.parse(text, lines or [])
    )
    return result, requests


def ollama(content):
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})


def test_commands_do_not_contact_server():
    result, requests = run("/lista", ollama("{}"))
    assert result.action == "list"
    assert requests == []


def test_natural_language_posts_minimal_list_to_loopback():
    line = ListLine(id="line-1", description="pan", quantity=2, revision=3, product_id="secret")
    result, requests = run(
        "necesito arroz",
        ollama(json.dumps({"action": "add", "lines": [{"description": "arroz"}]})),
        lines=[line],
    )
    assert result == Intent(action="add", lines=[{"description": "arroz"}])
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "http://127.0.0.1:11434/api/chat"
    body = json.loads(request.content)
    assert body["model"] == "gemma4:e2b"
    assert body["stream"] is False
    assert body["think"] is False
    assert body["format"] == Intent.model_json_schema()
    assert body["options"] == {"num_ctx": 4096}
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "system"
    assert json.loads(body["messages"][1]["content"]) == {
        "text": "necesito arroz", "lines": [{"id": "line-1", "description": "pan", "quantity": 2}],
        "products": [],
    }
    assert "secret" not in request.content.decode()
    assert "revision" not in request.content.decode()
    assert '"action":"add"' in body["messages"][0]["content"]
    assert "sin cantidad" in request.content.decode().lower()
    assert "necesito" in body["messages"][0]["content"]
    assert "NUNCA product_query" in body["messages"][0]["content"]


def test_list_query_receives_minimal_lines_and_returns_list():
    line = ListLine(id="line-42", description="arroz", quantity=None, revision=7)
    result, requests = run("¿qué hay en mi lista?", ollama('{"action":"list"}'), lines=[line])
    assert result.action == "list"
    content = json.loads(json.loads(requests[0].content)["messages"][1]["content"])
    assert content["lines"] == [{"id": "line-42", "description": "arroz", "quantity": None}]
    assert "lista" in json.loads(requests[0].content)["messages"][0]["content"].lower()


def test_context_caps_observations_and_omits_urls_private_fields_and_html():
    products = [
        ObservedProduct(
            id=f"id-{i}", store_id="nappy", product_id="diapers",
            title="<b>Dodot</b> pañales", url="https://example.org/token-SECRET",
            observed_on="2026-09-27", price_cents=1200, availability=None,
            format_note="<script>bad</script> 56 unidades",
        ) for i in range(8)
    ]
    result, requests = run(
        "¿qué pañales vimos?",
        ollama('{"action":"product_query","lines":[{"description":"pañales"}]}'),
        products=products, contextual=True,
    )
    assert result.action == "product_query"
    payload = requests[0].content.decode()
    data = json.loads(json.loads(requests[0].content)["messages"][1]["content"])
    assert set(data) == {"text", "lines", "products"}
    assert len(data["products"]) == 5
    assert data["products"][0] == {
        "title": "Dodot pañales", "store_id": "nappy", "observed_on": "2026-09-27",
        "price_cents": 1200, "availability": None, "format_note": "bad 56 unidades",
    }
    assert "token-SECRET" not in payload
    assert "<" not in json.dumps(data) and ">" not in json.dumps(data)
    assert "historial" not in json.dumps(data, ensure_ascii=False).lower()


@pytest.mark.parametrize("action", ["buy", "remove"])
def test_model_destructive_actions_rejected_by_conversation(action):
    from conversation import Conversation

    result, _ = run("no compres", ollama(json.dumps({"action": action})))
    assert Conversation._validate_model("no compres", result, []).action == "clarify"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"message": {"role": "assistant", "content": "no json"}}),
        ollama(json.dumps({"action": "refuse"})),
        httpx.Response(200, json={"message": {"role": "assistant", "content": ""}}),
        httpx.Response(503),
        httpx.Response(200, json={"message": {"role": "assistant", "content": "No."}, "done_reason": "unload"}),
    ],
)
def test_invalid_or_refused_response_clarifies_without_leaking_provider_data(response):
    result, _ = run("necesito arroz", response)
    assert result.action == "clarify"
    assert result.question
    assert "no json" not in result.question


def test_network_timeout_clarifies():
    def timeout(request):
        raise httpx.ReadTimeout("private text", request=request)

    result, _ = run("necesito arroz", timeout)
    assert result.action == "clarify"
    assert "private text" not in result.question


def test_explicit_model_refusal_cannot_become_an_addition():
    result, _ = run(
        "necesito arroz",
        httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"action": "add", "lines": [{"description": "arroz"}]}),
                    "refusal": "No puedo ayudar.",
                }
            },
        ),
    )
    assert result.action == "clarify"


def test_non_assistant_response_cannot_propose_intent():
    result, _ = run(
        "necesito arroz",
        httpx.Response(
            200,
            json={"message": {"role": "user", "content": json.dumps({"action": "list"})}},
        ),
    )
    assert result.action == "clarify"


def test_total_deadline_applies_even_when_read_timeout_does_not_fire(monkeypatch):
    async def slow(request):
        await asyncio.sleep(0.02)
        return ollama(json.dumps({"action": "list"}))

    # A short simulated deadline proves the wall-clock cancellation, without a 60s test.
    monkeypatch.setattr("ollama_interpreter.TOTAL_TIMEOUT", 0.001)
    async def execute():
        return await OllamaInterpreter(transport=httpx.MockTransport(slow)).parse("necesito arroz", [])

    result = asyncio.run(execute())
    assert result.action == "clarify"


def test_redirect_to_external_host_is_never_followed():
    result, requests = run(
        "necesito arroz", httpx.Response(302, headers={"location": "https://evil.example/collect"})
    )
    assert result.action == "clarify"
    assert [str(request.url) for request in requests] == ["http://127.0.0.1:11434/api/chat"]


def test_transport_injection_cannot_change_request_destination():
    result, requests = run("necesito arroz", ollama(json.dumps({"action": "list"})))
    assert result.action == "list"
    assert all(request.url.host == "127.0.0.1" for request in requests)


@pytest.mark.parametrize("text,action,name", [
    ("ahora pasta", "mention_product", "pasta"),
    ("necesito arroz", "add", "arroz"),
    ("necesito aroz", "add", "aroz"),
    ("QUIERO Arroz ÍNTEGRAL por favor", "add", "Arroz ÍNTEGRAL"),
    ("me hace falta Café molido", "add", "Café molido"),
    ("me hacen falta Dodot talla 4", "add", "Dodot talla 4"),
    ("ahora Blemil etapa 2", "mention_product", "Blemil etapa 2"),
])
def test_dialogue_schema_constrains_literal_whole_request(text, action, name):
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        # Exercise the emitted format boundary, not a fabricated interpreter result.
        success, refusal = body["format"]["anyOf"]
        assert success["properties"]["action"] == {"type": "string", "enum": [action]}
        line = success["properties"]["lines"]
        assert line["minItems"] == line["maxItems"] == 1
        item = line["items"]
        assert item["properties"]["description"] == {"type": "string", "enum": [name]}
        assert item["properties"]["quantity"] == {"type": "null"}
        assert item["additionalProperties"] is False
        assert success["additionalProperties"] is False
        assert set(success["properties"]) == {"action", "lines"}
        assert set(item["properties"]) == {"description", "quantity"}
        assert refusal["properties"]["action"]["enum"] == ["clarify"]
        return ollama(json.dumps({"action": action, "lines": [{"description": name, "quantity": None}]}))

    lines = [ListLine(id="private-line", description="arroz", quantity=2, revision=1)]
    model = OllamaInterpreter(transport=httpx.MockTransport(respond))
    result = asyncio.run(model.parse_with_dialogue(text, lines, [], None))
    assert result == Intent(action=action, lines=[{"description": name}])
    assert len(requests) == 1


@pytest.mark.parametrize("text,output", [
    ("ahora pasta", {"action": "add", "lines": [{"description": "pasta"}]}),
    ("necesito arroz", {"action": "add", "lines": [{"description": "arroz", "quantity": 2}]}),
    ("necesito aroz", {"action": "add", "lines": [{"description": "arroz"}]}),
    ("ahora Dodot talla 4", {"action": "mention_product", "lines": [{"description": "Dodot"}]}),
    ("necesito Arroz", {"action": "add", "lines": [{"description": "arroz"}]}),
    ("necesito arroz", {"action": "add", "lines": [{"description": "arroz", "line_id": "chosen"}]}),
    ("necesito arroz", {"action": "add", "lines": [{"description": "arroz"}], "order_id": "chosen"}),
])
def test_dialogue_provider_cannot_violate_source_constraints_or_be_repaired(text, output):
    model = OllamaInterpreter(transport=httpx.MockTransport(lambda request: ollama(json.dumps(output))))
    result = asyncio.run(model.parse_with_dialogue(text, [], [], None))
    assert result.action == "clarify"
    assert result.lines == []


@pytest.mark.parametrize("text,name", [
    ("ahora pasta si hay oferta", "pasta"),
    ("necesito arroz cuando haya oferta", "arroz"),
    ("no necesito arroz", "arroz"),
    ("necesito arroz no integral", "arroz"),
    ('necesito "arroz"', "arroz"),
    ("ahora arroz integral", "arroz"),
    ("necesito arroz y pasta", "arroz"),
    ("necesito 2 arroz", "arroz"),
    ("necesito por favor", "por"),
])
def test_source_constraints_do_not_bypass_unsafe_text_or_qualifier_guard(text, name):
    from dialogue_controller import validate_model

    action = "mention_product" if text.startswith("ahora") else "add"
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return ollama(json.dumps({"action": action, "lines": [{"description": name}]}))

    model = OllamaInterpreter(transport=httpx.MockTransport(respond))
    result = asyncio.run(model.parse_with_dialogue(text, [], [], None))
    assert validate_model(text, result, []).action == "clarify"
    if text != "ahora arroz integral":
        assert requests[0]["format"] == Intent.model_json_schema()


def test_dialogue_source_schema_allows_fail_closed_clarify():
    model = OllamaInterpreter(transport=httpx.MockTransport(lambda request: ollama('{"action":"clarify","lines":[]}')))
    result = asyncio.run(model.parse_with_dialogue("necesito arroz", [], [], None))
    assert result.action == "clarify" and result.lines == []


def test_dialogue_unknown_or_overlong_request_keeps_untrusted_route_bounded():
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return ollama('{"action":"clarify","lines":[]}')

    model = OllamaInterpreter(transport=httpx.MockTransport(respond))
    for text in ("hablamos de pasta", "necesito " + "arroz integral " * 20):
        assert asyncio.run(model.parse_with_dialogue(text, [], [], None)).action == "clarify"
    for body in requests:
        assert body["format"] == Intent.model_json_schema()
        assert len(json.loads(body["messages"][1]["content"])["text"]) <= 160


def test_dialogue_payload_bounded_and_no_history_or_control_flags():
    requests = []
    now = datetime(2026, 10, 1, tzinfo=UTC)
    lines = [
        ListLine(id=f"private-line-{i}", description=f"current-{i} " + "x" * 200,
                 quantity=2, revision=7, product_id="private-product")
        for i in range(25)
    ]
    state = DialogueState(
        user_id=987654, chat_id=876543,
        focus=ProductMention(description="<b>Dodot talla 4</b>" + "x" * 200,
                             source_update_id=765432, line=LineRef(id=lines[0].id, revision=7)),
        target=LineRef(id=lines[0].id, revision=7),
        candidates=tuple(LineRef(id=line.id, revision=7) for line in lines[18:]),
        question="add_or_replace", options=("add", "replace"), proposal_quantity=99,
        replacement_confirmed=True, duplicate_confirmed=True,
        updated_at=now, expires_at=now + timedelta(minutes=15),
    )
    products = [ObservedProduct(
        id=f"private-observation-{i}", store_id="private-store", product_id="private-product",
        title="<b>Dodot talla 4</b>" + "x" * 200, url="https://example.org/private-url",
        observed_on="2026-09-27", price_cents=1200, availability=None,
        format_note="<i>paquetes</i>" + "x" * 200,
    ) for i in range(8)]

    def capture(request):
        requests.append(request)
        return ollama('{"action":"mention_product","lines":[{"description":"Dodot talla 4"}]}')

    interpreter = OllamaInterpreter(transport=httpx.MockTransport(capture))
    result = asyncio.run(interpreter.parse_with_dialogue("ahora Dodot talla 4", lines, products, state))
    assert result.action == "mention_product" and result.lines[0].quantity is None
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    context = json.loads(body["messages"][1]["content"])
    assert body["options"]["num_ctx"] == 4096
    assert body["think"] is False and body["stream"] is False
    assert str(requests[0].url) == "http://127.0.0.1:11434/api/chat"
    assert len(body["messages"]) == 2
    assert len(context["lines"]) == 20 and len(context["products"]) == 5
    assert set(context["dialogue"]) == {"focus", "question", "options", "candidates"}
    assert context["dialogue"]["question"] == "add_or_replace"
    assert context["dialogue"]["options"] == ["add", "replace"]
    assert context["dialogue"]["focus"] == "Dodot talla 4" + "x" * 147
    assert context["dialogue"]["candidates"] == [
        f"current-{i} " + "x" * 149 for i in range(18, 23)
    ]
    assert all(set(line) == {"description", "quantity"} for line in context["lines"])
    assert all(set(product) == {"title", "price_cents", "availability", "format_note"}
               for product in context["products"])
    assert all(len(line["description"]) <= 160 for line in context["lines"])
    assert all(len(product["title"]) <= 160 and len(product["format_note"]) <= 160
               for product in context["products"])
    serialized = json.dumps(context)
    for forbidden in ("private-", "revision", "confirmed", "updated_at", "expires_at",
                      "source_update_id", "observed_on", "history", "transcript", "configuration"):
        assert forbidden not in serialized
    assert "<" not in serialized and ">" not in serialized


def test_dialogue_candidates_resolve_only_current_revisions_and_options_are_action_keys():
    now = datetime(2026, 10, 1, tzinfo=UTC)
    state = DialogueState(
        user_id=7, chat_id=7, focus=None, question="select_line",
        candidates=(LineRef(id="deleted", revision=1), LineRef(id="stale", revision=1),
                    LineRef(id="current", revision=2)),
        options=("change_quantity", "buy", "permission-secret"),
        updated_at=now, expires_at=now + timedelta(minutes=15),
    )
    requests = []

    def capture(request):
        requests.append(request)
        return ollama('{"action":"clarify"}')

    asyncio.run(OllamaInterpreter(transport=httpx.MockTransport(capture)).parse_with_dialogue(
        "a" * 200, [ListLine(id="stale", revision=2, description="old"),
                    ListLine(id="current", revision=2, description="current name")], [], state,
    ))
    context = json.loads(json.loads(requests[0].content)["messages"][1]["content"])
    assert context["dialogue"] == {
        "focus": None, "question": "select_line", "options": ["change_quantity"],
        "candidates": ["current name"],
    }
    assert context["text"] == "a" * 160


def test_dialogue_none_is_explicit_and_slash_skips_http():
    requests = []

    def capture(request):
        requests.append(request)
        return ollama('{"action":"list"}')

    interpreter = OllamaInterpreter(transport=httpx.MockTransport(capture))
    result = asyncio.run(interpreter.parse_with_dialogue("mi lista", [], [], None))
    assert result.action == "list"
    context = json.loads(json.loads(requests[0].content)["messages"][1]["content"])
    assert context == {"text": "mi lista", "lines": [], "products": [], "dialogue": None}
    result = asyncio.run(interpreter.parse_with_dialogue("/lista", [], [], None))
    assert result.action == "list" and len(requests) == 1
