import asyncio
import json

import httpx
import pytest

from domain import Intent, ListLine
from ollama_interpreter import OllamaInterpreter


def run(text, response, *, lines=None):
    requests = []

    async def transport(request):
        requests.append(request)
        return response(request) if callable(response) else response

    interpreter = OllamaInterpreter(transport=httpx.MockTransport(transport))
    result = asyncio.run(interpreter.parse(text, lines or []))
    return result, requests


def ollama(content):
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})


def test_commands_do_not_contact_server():
    result, requests = run("/lista", ollama("{}"))
    assert result.action == "list"
    assert requests == []


def test_natural_language_posts_only_current_text_without_list_to_loopback():
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
        "text": "necesito arroz",
    }
    assert "secret" not in request.content.decode()
    assert "pan" not in request.content.decode()


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
