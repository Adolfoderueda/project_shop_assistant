"""Offline regressions derived from the reviewed 12B semantic failures."""

import asyncio
from datetime import UTC, datetime

import httpx

from conversation import Conversation
from domain import IncomingMessage
from runtime import _CommandsOnly
from shopping_agent.conversation import AgentConversation
from shopping_agent.ollama import OllamaShoppingAgent
from storage import Repository
from tests.dialogue_support import seed_line

NOW = datetime(2026, 10, 14, tzinfo=UTC)


def _repo(tmp_path):
    repo = Repository(tmp_path / "real12b-correction.db")
    repo.migrate()
    return repo


def _ingest(repo, update_id, text, *, user_id=7):
    repo.ingest_batch([IncomingMessage(
        update_id=update_id, user_id=user_id, chat_id=user_id, text=text,
    )], update_id + 1)


def test_unique_resolved_target_uses_exact_descriptor_through_unknown_base(tmp_path):
    repo = _repo(tmp_path)
    target = seed_line(repo, "arroz blanco", None)
    _ingest(repo, 2, "Quiero tres envases mas de arroz")
    repo.apply_agent_operation(2, "proponer_cambio", {
        "kind": "increment", "query": "arroz", "quantity": 3, "unit": "envases",
    }, None, now=NOW)
    proposal = repo.agent_snapshot(2, now=NOW).proposal
    assert proposal.original_text == "Quiero tres envases mas de arroz"
    assert proposal.items[0].target.id == target.id
    assert proposal.items[0].description == "arroz"
    assert proposal.items[0].base_quantity is None
    assert not repo.list_lines()[0].quantity

    _ingest(repo, 3, "cambiar cantidad")
    repo.apply_agent_control(3, now=NOW)
    _ingest(repo, 4, "7 envases")
    repo.apply_agent_control(4, now=NOW)
    proposal = repo.agent_snapshot(4, now=NOW).proposal
    assert proposal.items[0].kind == "set_quantity"
    assert proposal.items[0].description == "arroz blanco"
    assert proposal.items[0].quantity == 7
    assert repo.list_lines()[0].quantity is None
    repo = Repository(repo.path)  # The exact descriptor survives a restart.
    assert repo.agent_snapshot(4, now=NOW).proposal.items[0].description == "arroz blanco"
    _ingest(repo, 5, "sí")
    reply = repo.apply_agent_control(5, now=NOW)
    assert repo.apply_agent_control(5, now=NOW) == reply
    assert [(row.id, row.description, row.quantity) for row in repo.list_lines()] == [
        (target.id, "arroz blanco", 7),
    ]


def test_native_ambiguous_change_waits_for_explicit_selection(tmp_path):
    repo = _repo(tmp_path)
    white = seed_line(repo, "arroz blanco", 2)
    seed_line(repo, "arroz integral", 4)
    message = IncomingMessage(update_id=3, user_id=7, chat_id=7,
                              text="Quiero tres envases mas de arroz")
    repo.ingest_batch([message], 4)

    def respond(_request):
        return httpx.Response(200, json={
            "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": "", "tool_calls": [{
                "function": {"name": "proponer_cambio", "arguments": {
                    "kind": "increment", "query": "arroz", "quantity": 3, "unit": "envases",
                }},
            }]},
        })

    conversation = AgentConversation(
        repo, OllamaShoppingAgent(transport=httpx.MockTransport(respond)),
        Conversation(repo, _CommandsOnly(), clock=lambda: NOW), clock=lambda: NOW,
    )
    reply = asyncio.run(conversation.handle(message, "dry_run"))
    proposal = repo.agent_snapshot(3, now=NOW).proposal
    assert proposal.items[0].target is None
    assert len(proposal.items[0].candidates) == 2
    assert "arroz blanco" in reply.text and "arroz integral" in reply.text
    assert [row.quantity for row in repo.list_lines()] == [2, 4]

    _ingest(repo, 4, "1")
    repo.apply_agent_control(4, now=NOW)
    proposal = repo.agent_snapshot(4, now=NOW).proposal
    assert proposal.items[0].target.id == white.id
    assert proposal.items[0].description == "arroz"
    assert proposal.items[0].quantity == 5
    assert [row.quantity for row in repo.list_lines()] == [2, 4]


def test_unknown_base_total_rejects_changed_row_and_foreign_confirmation(tmp_path):
    repo = _repo(tmp_path)
    target = seed_line(repo, "arroz blanco", None)
    _ingest(repo, 2, "Quiero tres envases mas de arroz")
    repo.apply_agent_operation(2, "proponer_cambio", {
        "kind": "increment", "query": "arroz", "quantity": 3,
    }, None, now=NOW)
    _ingest(repo, 3, "cambiar cantidad")
    repo.apply_agent_control(3, now=NOW)
    _ingest(repo, 4, "7 envases")
    repo.apply_agent_control(4, now=NOW)
    assert repo.agent_snapshot(4, now=NOW).proposal.items[0].description == "arroz blanco"

    _ingest(repo, 5, "sí", user_id=8)
    repo.apply_agent_control(5, now=NOW)
    assert repo.agent_snapshot(4, now=NOW).proposal is not None
    assert repo.list_lines()[0].quantity is None

    with repo._connection(write=True) as db:
        db.execute("UPDATE list_lines SET quantity=9, revision=revision+1 WHERE id=?", (target.id,))
    _ingest(repo, 6, "sí")
    repo.apply_agent_control(6, now=NOW)
    assert [(row.id, row.quantity) for row in repo.list_lines()] == [(target.id, 9)]
    assert repo.agent_snapshot(6, now=NOW).proposal is None


def test_no_native_tool_call_remains_clarification_without_draft(tmp_path):
    repo = _repo(tmp_path)
    seed_line(repo, "arroz blanco", 2)
    seed_line(repo, "arroz integral", 4)
    message = IncomingMessage(update_id=3, user_id=7, chat_id=7,
                              text="Quiero tres envases mas de arroz")
    repo.ingest_batch([message], 4)

    def respond(_request):
        return httpx.Response(200, json={
            "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": "Necesito aclaración", "tool_calls": []},
        })

    conversation = AgentConversation(
        repo, OllamaShoppingAgent(transport=httpx.MockTransport(respond)),
        Conversation(repo, _CommandsOnly(), clock=lambda: NOW), clock=lambda: NOW,
    )
    reply = asyncio.run(conversation.handle(message, "dry_run"))
    assert "Aclara" in reply.text
    assert repo.agent_snapshot(3, now=NOW).proposal is None
    assert [row.quantity for row in repo.list_lines()] == [2, 4]
