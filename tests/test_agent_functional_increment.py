"""Synthetic native-tool boundary cases from the historical E4B failures."""

import asyncio
from datetime import UTC, datetime

import httpx

from conversation import Conversation
from domain import IncomingMessage
from runtime import _CommandsOnly
from shopping_agent.conversation import AgentConversation
from shopping_agent.ollama import OllamaShoppingAgent
from storage import Repository

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)


def _call(name, arguments=None):
    return {"function": {"name": name, "arguments": arguments or {}}}


def _send(repo, update_id, text, calls):
    responses = iter([
        {"role": "assistant", "content": "Guardado y comprado", "tool_calls": calls},
        {"role": "assistant", "content": "El borrador está guardado"},
    ])

    def respond(_request):
        return httpx.Response(200, json={"done": True, "done_reason": "stop",
                                         "message": next(responses)})

    message = IncomingMessage(update_id=update_id, user_id=7, chat_id=7, text=text)
    repo.ingest_batch([message], update_id + 1)
    conversation = AgentConversation(
        repo, OllamaShoppingAgent(transport=httpx.MockTransport(respond)),
        Conversation(repo, _CommandsOnly(), clock=lambda: NOW), clock=lambda: NOW)
    return asyncio.run(conversation.handle(message, "dry_run"))


def test_saved_list_read_with_pending_draft_uses_repository_facts(tmp_path):
    repo = Repository(tmp_path / "synthetic.db")
    repo.migrate()
    repo.ingest_batch([IncomingMessage(update_id=0, user_id=7, chat_id=7,
                                      text="synthetic seed")], 1)
    with repo._connection(write=True) as db:
        db.execute("INSERT INTO list_lines VALUES (?,?,?,?,1,?)",
                   ("saved-1", None, "pan", 4, 0))
    _send(repo, 1, "Apunta dos envases de lentejas", [
        _call("proponer_altas", {"items": [{"description": "lentejas", "quantity": 2}]})])
    before = repo.agent_snapshot(1, now=NOW).proposal
    reply = _send(repo, 2, "Muéstrame lo que ya está apuntado para comprar", [
        _call("consultar_lista")])
    assert "pan" in reply.text and "4 envases" in reply.text
    assert "lentejas" not in reply.text and "Guardado y comprado" not in reply.text
    assert repo.agent_snapshot(2, now=NOW).proposal == before
    assert [(row.description, row.quantity) for row in repo.list_lines()] == [("pan", 4)]


def test_internal_duplicate_requires_both_decisions_before_commit(tmp_path):
    repo = Repository(tmp_path / "synthetic.db")
    repo.migrate()
    _send(repo, 1, "Necesito dos envases de arroz y otros tres en otra entrada", [
        _call("proponer_altas", {"items": [
            {"description": "arroz", "quantity": 2},
            {"description": "arroz", "quantity": 3},
        ]})])
    incomplete = _send(repo, 2, "Mantén cada entrada como línea separada", [
        _call("completar_propuesta", {"patches": [
            {"position": 1, "quantity": 2}, {"position": 2, "quantity": 3}]})])
    assert "posición 1" in incomplete.text and "posición 2" in incomplete.text
    assert "decisión" in incomplete.text.lower()
    assert not repo.list_lines()
    _send(repo, 3, "sí", [])
    assert not repo.list_lines()
    review = _send(repo, 4, "Dos líneas separadas", [
        _call("completar_propuesta", {"patches": [
            {"position": 1, "duplicate_decision": "separate"},
            {"position": 2, "duplicate_decision": "separate"},
        ]})])
    assert "¿Confirmas?" in review.text and not repo.list_lines()
    committed = _send(repo, 5, "sí", [])
    assert "Lote guardado: 2" in committed.text
    assert [(row.description, row.quantity) for row in repo.list_lines()] == [
        ("arroz", 2), ("arroz", 3)]
    assert _send(repo, 5, "sí", []) == committed
    assert len(repo.list_lines()) == 2
