"""Offline contracts for the isolated 12B deployment profile."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from config import Settings, load_settings, save_settings
from domain import IncomingMessage, Intent, IntentLine
from storage import Repository

MODEL = "gemma4-12b-shop:16k"
ENDPOINT = "http://127.0.0.1:11435"


def _settings(tmp_path, **changes):
    return Settings(
        telegram_token="synthetic-token",
        authorized_user_id=7,
        address="synthetic-address",
        database_path=tmp_path / "private" / "assistant.db",
        **changes,
    )


def test_12b_requires_dedicated_endpoint_dry_run_and_purchase_block(tmp_path):
    selected = _settings(
        tmp_path, model_provider="ollama", conversation_engine="skills_agent",
        agent_model=MODEL, agent_endpoint=ENDPOINT, experimental_no_purchases=True,
    )
    assert selected.mode == "dry_run"
    assert _settings(tmp_path).agent_model == "gemma4:e4b-it-q4_K_M"
    for changes in (
        {"agent_model": MODEL},
        {"agent_model": MODEL, "agent_endpoint": ENDPOINT},
        {"agent_model": MODEL, "experimental_no_purchases": True},
        {"mode": "live", "experimental_no_purchases": True},
        {"agent_endpoint": "http://example.com:11435"},
    ):
        with pytest.raises(ValueError):
            _settings(tmp_path, **changes)


@pytest.mark.parametrize("guided", [False, True])
def test_12b_uses_dedicated_transport_and_profile_without_network(tmp_path, guided):
    from shopping_agent.contracts import AgentSnapshot
    from shopping_agent.guided_contracts import GuidedState
    from shopping_agent.guided_ollama import GuidedOllamaAgent
    from shopping_agent.ollama import OllamaShoppingAgent
    from shopping_agent.tools import AgentTools

    agent_type = GuidedOllamaAgent if guided else OllamaShoppingAgent
    with pytest.raises(ValueError):
        agent_type(MODEL)
    repo = Repository(tmp_path / "probe.db")
    repo.migrate()
    event = IncomingMessage(update_id=1, user_id=7, chat_id=7, text="necesito arroz")
    repo.ingest_batch([event], 2)

    def respond(request):
        assert str(request.url) == ENDPOINT + "/api/chat"
        payload = json.loads(request.content)
        assert payload["model"] == MODEL
        assert payload["think"] is True
        assert payload["keep_alive"] == "30m"
        assert payload["options"]["num_ctx"] == 16384
        assert len(payload["tools"]) == 7 if not guided else len(payload["tools"]) > 0
        return httpx.Response(200, json={
            "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": "", "tool_calls": [{
                "function": {"name": "proponer_altas",
                             "arguments": {"items": [{"description": "arroz"}]}}
            }]},
        })

    transport = httpx.MockTransport(respond)
    agent = agent_type(MODEL, endpoint=ENDPOINT, transport=transport)
    if guided:
        state = GuidedState(snapshot=AgentSnapshot(
            user_id=7, chat_id=7, source_update_id=1, original_text=event.text,
        ))
        result = asyncio.run(agent.interpret(event, state, ()))
        assert result.reason == "candidate"
    else:
        result = asyncio.run(agent.run(
            event, AgentTools(repo, event, now=datetime(2026, 10, 14, tzinfo=UTC)),
        ))
        assert result.reason == "terminal"
    assert repo.list_lines() == []


def test_blocked_buy_preserves_guided_list_proposal_and_replay(tmp_path):
    from runtime import _PurchasesBlocked
    from tests.guided_helpers import persisted_case

    case = persisted_case(tmp_path, quantities=(1, 2, 3))
    case.repo.purchases_enabled = False
    question = case.question()
    before = case.repo.guided_state(1, now=case.now).snapshot.proposal
    assert before is not None
    case.ingest_message(2, "/comprar")
    event, _ = case.repo.message_result(2)

    class NeverConversation:
        async def handle(self, *_):
            pytest.fail("Blocked buy reached conversation")

    guard = _PurchasesBlocked(case.repo, NeverConversation())
    reply = asyncio.run(guard.handle(event, "dry_run"))
    assert "bloquead" in reply.text.lower()
    assert case.repo.guided_state(2, now=case.now).snapshot.proposal == before
    assert asyncio.run(guard.handle(event, "dry_run")) == reply
    assert case.repo.guided_state(2, now=case.now).snapshot.proposal == before
    assert case.repo.list_lines() == []
    assert question is not None

    # A prior list review remains usable and commits only through its own callback.
    token = case.choice_token("confirm")
    case.record_known_delivery()
    case.ingest_callback(3, token)
    case.repo.apply_guided_callback(3, now=case.now)
    assert sorted(line.quantity for line in case.repo.list_lines()) == [1, 2, 3]


def test_repository_refuses_direct_buy_and_resume_without_consuming_inbox(tmp_path):
    repo = Repository(tmp_path / "blocked.db", purchases_enabled=False)
    repo.migrate()
    for update_id, action in ((1, "buy"), (2, "resume")):
        event = IncomingMessage(update_id=update_id, user_id=7, chat_id=7, text="/" + action)
        repo.ingest_batch([event], update_id + 1)
        with pytest.raises(PermissionError):
            repo.apply_intent(
                update_id, Intent(action=action, order_id="historical" if action == "resume" else None),
                "dry_run",
            )
        assert repo.message_result(update_id)[1] is None


def test_repository_refuses_dialogue_purchase_without_consume(tmp_path):
    repo = Repository(tmp_path / "blocked.db", purchases_enabled=False)
    repo.migrate()
    repo.ingest_batch([IncomingMessage(
        update_id=1, user_id=7, chat_id=7, text="compra lo pendiente",
    )], 2)
    with pytest.raises(PermissionError):
        repo.apply_dialogue(1, None, "dry_run", now=datetime(2026, 10, 14, tzinfo=UTC))
    assert repo.message_result(1)[1] is None
    assert repo.pending_orders() == []


def test_cli_selects_12b_only_with_purchase_block_and_keeps_binding(tmp_path, monkeypatch):
    import cli

    initial = _settings(tmp_path)
    save_settings(tmp_path, initial)

    async def available(model, *, endpoint):
        assert (model, endpoint) == (MODEL, ENDPOINT)
        return True

    monkeypatch.setattr(cli, "ollama_available", available)
    with pytest.raises(ValueError):
        asyncio.run(cli.agent_local(tmp_path, "enable", model=MODEL))
    assert load_settings(tmp_path).agent_model == initial.agent_model
    assert asyncio.run(cli.agent_local(
        tmp_path, "enable", model=MODEL, experimental_no_purchases=True
    ))
    selected = load_settings(tmp_path)
    assert (selected.agent_model, selected.agent_endpoint) == (MODEL, ENDPOINT)
    assert selected.experimental_no_purchases and selected.mode == "dry_run"
    assert selected.telegram_token == initial.telegram_token
    assert selected.authorized_user_id == initial.authorized_user_id


def test_experimental_runtime_keeps_existing_order_pending(tmp_path):
    from runtime import run

    configured = _settings(
        tmp_path, model_provider="ollama", conversation_engine="skills_agent",
        agent_model=MODEL, agent_endpoint=ENDPOINT, experimental_no_purchases=True,
    )
    repo = Repository(configured.database_path)
    repo.migrate()
    repo.ingest_batch([IncomingMessage(update_id=1, user_id=7, chat_id=7, text="/anadir arroz")], 2)
    repo.apply_intent(1, Intent(action="add", lines=[IntentLine(description="arroz", quantity=2)]), "dry_run")
    repo.ingest_batch([IncomingMessage(update_id=2, user_id=7, chat_id=7, text="/comprar")], 3)
    order = repo.apply_intent(2, Intent(action="buy"), "dry_run")
    assert order.order_id in repo.pending_orders()
    repo.purchases_enabled = False
    with pytest.raises(PermissionError):
        repo.claim_order(order.order_id)
    with pytest.raises(PermissionError):
        repo.reclaim_abandoned_orders()
    assert repo.order_status(order.order_id) == "pendiente"

    class NeverRecovery:
        async def recover(self):
            pytest.fail("Purchase recovery ran in blocked profile")

    class NeverCheckout:
        async def run(self, _):
            pytest.fail("Checkout ran in blocked profile")

    class Transport:
        async def ack_callbacks(self):
            pass

        async def send_pending(self):
            pass

        async def poll_once(self):
            raise asyncio.CancelledError

    class Conversation:
        async def handle(self, *_):
            pytest.fail("Unexpected pending conversation")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(
            configured, repo=repo, recovery=NeverRecovery(), checkout=NeverCheckout(),
            transport=Transport(), conversation=Conversation(),
        ))
    assert order.order_id in repo.pending_orders()
    assert repo.list_lines()[0].quantity == 2


def test_runtime_routes_12b_to_fixed_endpoint_without_opening_stores(tmp_path, monkeypatch):
    import shopping_agent.guided_ollama
    from runtime import run

    configured = _settings(
        tmp_path, model_provider="ollama", conversation_engine="skills_agent",
        guided_questions=True, agent_model=MODEL, agent_endpoint=ENDPOINT,
        experimental_no_purchases=True,
    )
    repo = Repository(configured.database_path)
    repo.migrate()
    constructed = []

    def guided_agent(model, **kwargs):
        constructed.append((model, kwargs))
        return object()

    monkeypatch.setattr(shopping_agent.guided_ollama, "GuidedOllamaAgent", guided_agent)

    class Transport:
        async def ack_callbacks(self):
            pass

        async def send_pending(self):
            pass

        async def poll_once(self):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(configured, repo=repo, transport=Transport()))
    assert constructed == [(MODEL, {"endpoint": ENDPOINT})]
