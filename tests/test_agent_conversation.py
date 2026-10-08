import asyncio
from datetime import UTC, datetime

import pytest

from conversation import Conversation
from domain import IncomingMessage
from runtime import _CommandsOnly
from storage import Repository

NOW = datetime(2026, 10, 8, tzinfo=UTC)


@pytest.fixture
def setup(tmp_path):
    from shopping_agent.conversation import AgentConversation
    repo = Repository(tmp_path / 'agent.db')
    repo.migrate()

    class Agent:
        calls = 0

        async def run(self, message, tools):
            self.calls += 1
            from shopping_agent.contracts import AgentRunResult, ToolCall
            call = ToolCall(name='proponer_altas', arguments={'items': [{'description': 'arroz', 'quantity': 2}]})
            tools.validate_calls((call,))
            result = tools.execute(call)
            return AgentRunResult(reply=result.reply, model_calls=1, tool_calls=1, reason='terminal')

    agent = Agent()
    legacy = Conversation(repo, _CommandsOnly(), clock=lambda: NOW)
    return repo, agent, AgentConversation(repo, agent, legacy, clock=lambda: NOW)


def send(setup, update, text):
    repo, _, conversation = setup
    message = IncomingMessage(update_id=update, user_id=7, chat_id=7, text=text)
    repo.ingest_batch([message], update + 1)
    return asyncio.run(conversation.handle(message, 'dry_run'))


def test_natural_alias_never_falls_into_old_parser(setup):
    send(setup, 1, 'añade 2 arroz')
    assert setup[1].calls == 1
    assert not setup[0].list_lines()


def test_complete_yes_control_calls_no_model(setup):
    send(setup, 1, 'arroz')
    send(setup, 2, 'sí')
    send(setup, 3, 'sí')
    assert setup[1].calls == 1
    assert len(setup[0].list_lines()) == 1


def test_mixed_yes_edit_uses_agent_and_new_review(setup):
    send(setup, 1, 'arroz')
    send(setup, 2, 'sí pero mejor dos')
    assert setup[1].calls == 2
    assert not setup[0].list_lines()


def test_known_greeting_reads_no_rows_and_preserves_pending(setup, monkeypatch):
    send(setup, 1, 'arroz')
    before = setup[0].agent_snapshot(1, now=NOW).proposal
    with monkeypatch.context() as patch:
        patch.setattr(setup[0], '_lines', lambda _: pytest.fail('private rows read'))
        send(setup, 2, 'hola')
    assert setup[0].agent_snapshot(2, now=NOW).proposal == before
    assert setup[1].calls == 1


def test_commands_purchase_and_command_origin_continuations_stay_legacy(setup):
    send(setup, 1, '/anadir arroz')
    assert setup[0].command_origin(7, 7).update_id == 1
    send(setup, 2, '2')
    assert [(l.description, l.quantity) for l in setup[0].list_lines()] == [('arroz', 2)]
    assert setup[0].command_origin(7, 7) is None
    send(setup, 3, '/comprar')
    assert setup[1].calls == 0


def test_durable_results_and_old_presentations_precede_agent(setup, monkeypatch):
    reply = send(setup, 1, 'arroz')
    monkeypatch.setattr(setup[0], 'set_conversation_route', lambda *a, **k: pytest.fail('route read'))
    message = setup[0].message_result(1)[0]
    assert asyncio.run(setup[2].handle(message, 'dry_run')) == reply


def test_enable_disable_does_not_resurrect_proposal(setup):
    send(setup, 1, 'arroz')
    legacy = Conversation(setup[0], _CommandsOnly(), clock=lambda: NOW, synchronize_route=True)
    message = IncomingMessage(update_id=2, user_id=7, chat_id=7, text='hola')
    setup[0].ingest_batch([message], 3)
    asyncio.run(legacy.handle(message, 'dry_run'))
    send(setup, 3, 'sí')
    assert not setup[0].list_lines()


def test_committed_presentation_precedes_context_even_after_rollback(setup, monkeypatch):
    from domain import Intent
    repo = setup[0]
    message = IncomingMessage(update_id=1, user_id=7, chat_id=7, text='hola')
    repo.ingest_batch([message], 2)
    prepared = repo.prepare_dialogue(1, Intent(action='greet'), 'dry_run', now=NOW)
    monkeypatch.setattr(repo, 'set_conversation_route', lambda *a, **k: pytest.fail('route read'))
    assert asyncio.run(setup[2].handle(message, 'dry_run')) == prepared.snapshot.fallback
    assert setup[1].calls == 0


def test_duplicate_slash_add_quantity_continuation(setup):
    send(setup, 1, '/anadir 1 arroz')
    send(setup, 2, '/anadir arroz')
    send(setup, 3, 'añadir otra línea')
    assert setup[0].command_origin(7, 7).update_id == 2
    send(setup, 4, '2')
    assert len(setup[0].list_lines()) == 2
    assert setup[1].calls == 0


def test_origin_recording_rolls_back_with_transition(setup, monkeypatch):
    repo = setup[0]
    monkeypatch.setattr(repo, '_record_command_origin', lambda *a: (_ for _ in ()).throw(RuntimeError('fail')))
    with pytest.raises(RuntimeError):
        send(setup, 1, '/anadir arroz')
    assert repo.dialogue_state(7, 7, now=NOW) is None
    assert repo.message_result(1)[1] is None


def test_incompatible_pending_state_clears_command_link(setup):
    send(setup, 1, '/anadir arroz')
    # A different pending legacy proposal must not retain the slash permission.
    from domain import Intent, IntentLine
    message = IncomingMessage(update_id=2, user_id=7, chat_id=7, text='necesito pan')
    setup[0].ingest_batch([message], 3)
    setup[0].apply_dialogue(2, Intent(action='add', lines=[IntentLine(description='pan')]), 'dry_run', now=NOW)
    with setup[0]._connection() as db:
        assert db.execute('SELECT command_update_id FROM conversation_routes').fetchone()[0] is None


def test_route_discard_emits_controlled_notice(setup, caplog):
    send(setup, 1, 'arroz')
    setup[0].set_conversation_route(7, 7, 'legacy', now=NOW)
    assert 'Incompatible conversation memory discarded' in caplog.text
    assert 'arroz' not in caplog.text


def test_native_agent_prose_discarded_and_queries_preserve_proposal_ttl(setup):
    import httpx

    from shopping_agent.ollama import OllamaShoppingAgent
    send(setup, 1, 'arroz')
    before = setup[0].agent_snapshot(1, now=NOW).proposal
    responses = iter([
        {'tool_calls': [{'function': {'name': 'consultar_lista', 'arguments': {}}}], 'content': 'PRIVATE invented prose'},
        {'content': 'PRIVATE invented prose'},
    ])

    def respond(request):
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop',
                                       'message': {'role': 'assistant', **next(responses)}})

    setup[2].agent = OllamaShoppingAgent(transport=httpx.MockTransport(respond))
    reply = send(setup, 2, 'qué tengo')
    assert 'PRIVATE' not in reply.text
    assert setup[0].agent_snapshot(2, now=NOW).proposal == before


def test_first_legacy_route_does_not_discard_existing_legacy_memory(tmp_path):
    repo = Repository(tmp_path / 'agent.db')
    repo.migrate()
    from domain import Intent, IntentLine
    class Interpreter:
        async def parse(self, text, lines):
            return Intent(action='add', lines=[IntentLine(description='arroz')])
    conversation = Conversation(repo, Interpreter(), clock=lambda: NOW)
    first = IncomingMessage(update_id=1, user_id=7, chat_id=7, text='necesito arroz')
    repo.ingest_batch([first], 2)
    asyncio.run(conversation.handle(first, 'dry_run'))
    before = repo.dialogue_state(7, 7, now=NOW)
    assert before is not None
    conversation.synchronize_route = True
    greeting = IncomingMessage(update_id=2, user_id=7, chat_id=7, text='hola')
    repo.ingest_batch([greeting], 3)
    asyncio.run(conversation.handle(greeting, 'dry_run'))
    assert repo.dialogue_state(7, 7, now=NOW) == before


def test_slash_query_preserves_proposal_and_command_continuation(setup):
    send(setup, 1, 'arroz')
    before = setup[0].agent_snapshot(1, now=NOW).proposal
    send(setup, 2, '/lista')
    assert setup[0].agent_snapshot(2, now=NOW).proposal == before
    send(setup, 3, '/anadir pan')
    send(setup, 4, '/lista')
    assert setup[0].command_origin(7, 7).update_id == 3
