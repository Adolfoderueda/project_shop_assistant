import asyncio
from datetime import UTC, datetime

import pytest

import cli
from config import Settings, load_settings, save_settings
from domain import IncomingCallback
from runtime import ProcessLock
from tests.guided_helpers import VALID_TOKEN, persisted_case


def settings(tmp_path, **updates):
    return Settings(telegram_token='test-token', authorized_user_id=7, address='test-address',
        database_path=tmp_path / 'private' / 'assistant.db', **updates)


def test_guided_default_false_and_provider_validation(tmp_path):
    assert settings(tmp_path).guided_questions is False
    for updates in ({}, {'model_provider': 'ollama'}, {'conversation_engine': 'skills_agent'}):
        with pytest.raises(ValueError):
            settings(tmp_path, guided_questions=True, **updates)
    assert settings(tmp_path, guided_questions=True, conversation_engine='skills_agent',
                    model_provider='ollama').guided_questions


def local_case(tmp_path):
    private = tmp_path / 'private'
    private.mkdir()
    c = persisted_case(private)
    save_settings(tmp_path, settings(tmp_path, model_provider='ollama',
        conversation_engine='skills_agent').model_copy(update={'database_path': c.repo.path}))
    return c


def test_guided_status_is_read_only_with_worker_lock(tmp_path, monkeypatch):
    c = local_case(tmp_path)
    target = tmp_path / 'private' / 'settings.json'
    before = target.read_bytes()
    monkeypatch.chdir(tmp_path)
    with ProcessLock(c.repo.path.parent / 'worker.lock'):
        assert cli.main(['questions-local', 'status']) == 0
    assert target.read_bytes() == before
    assert c.question() is not None


def test_enable_disable_revokes_before_save_and_schema10_rollback(tmp_path, monkeypatch):
    c = local_case(tmp_path)
    c.ingest_message(2, '/anadir 1 arroz')
    c.repo.apply_dialogue(2, None, 'dry_run', now=c.now)
    saved = c.repo.list_lines()
    assert len(saved) == 1
    async def available(model):
        assert model == 'gemma4:e4b-it-q4_K_M'
        return True
    monkeypatch.setattr(cli, 'ollama_available', available)
    with ProcessLock(c.repo.path.parent / 'worker.lock'):
        assert not asyncio.run(cli.guided_local(tmp_path, 'enable'))
    assert asyncio.run(cli.guided_local(tmp_path, 'enable'))
    assert load_settings(tmp_path).guided_questions is True
    assert c.repo.guided_state(1, now=c.now).snapshot.proposal is None
    assert asyncio.run(cli.guided_local(tmp_path, 'disable'))
    assert load_settings(tmp_path).guided_questions is False
    assert c.repo.list_lines() == saved
    with c.repo._connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 10


def test_failed_settings_save_cannot_restore_guided_permission(tmp_path, monkeypatch):
    c = local_case(tmp_path)
    monkeypatch.setattr(cli, 'save_settings', lambda *a: (_ for _ in ()).throw(OSError('fail')))
    with pytest.raises(OSError):
        asyncio.run(cli.guided_local(tmp_path, 'disable'))
    assert c.repo.guided_state(1, now=c.now).snapshot.proposal is None
    assert c.repo.list_lines() == []


@pytest.mark.parametrize('command', ['agent_local', 'model_local'])
def test_disabling_engine_forces_guided_off(tmp_path, command):
    c = local_case(tmp_path)
    current = load_settings(tmp_path).model_copy(update={'guided_questions': True})
    save_settings(tmp_path, current)
    assert asyncio.run(getattr(cli, command)(tmp_path, 'disable'))
    assert load_settings(tmp_path).guided_questions is False
    assert c.repo.guided_state(1, now=c.now).snapshot.proposal is None


def test_enable_requires_selected_engine_and_model(tmp_path, monkeypatch):
    save_settings(tmp_path, settings(tmp_path))
    async def unavailable(model):
        return False
    monkeypatch.setattr(cli, 'ollama_available', unavailable)
    assert not asyncio.run(cli.guided_local(tmp_path, 'enable'))
    save_settings(tmp_path, settings(tmp_path, conversation_engine='skills_agent', model_provider='ollama'))
    assert not asyncio.run(cli.guided_local(tmp_path, 'enable'))
    assert load_settings(tmp_path).guided_questions is False


@pytest.mark.parametrize('flag', [False, True])
def test_runtime_typed_dispatch_ack_owner_and_selected_construction(tmp_path, monkeypatch, flag):
    import runtime
    import shopping_agent.guided_ollama
    import shopping_agent.ollama
    from tests.guided_helpers import PurchaseBlockedRepository, message

    repo = PurchaseBlockedRepository(tmp_path / 'private' / 'guided.db')
    repo.migrate()
    callback = IncomingCallback(update_id=1, user_id=7, chat_id=7, callback_query_id='retained',
        message_id=1, bot_id=99, data=VALID_TOKEN)
    repo.ingest_events([callback, message(2, '/lista')], 3)
    sequence = []
    original = repo.assert_authorized_owner
    def owner(user):
        sequence.append('owner')
        return original(user)
    monkeypatch.setattr(repo, 'assert_authorized_owner', owner)
    original_model = shopping_agent.guided_ollama.GuidedOllamaAgent
    def guided_model(name):
        sequence.append('guided_model')
        return original_model(name)
    def legacy_model(name):
        sequence.append('agent_model')
        return object()
    monkeypatch.setattr(shopping_agent.guided_ollama, 'GuidedOllamaAgent', guided_model)
    monkeypatch.setattr(shopping_agent.ollama, 'OllamaShoppingAgent', legacy_model)
    original_callback = repo.apply_guided_callback
    def apply(update, **kwargs):
        assert sequence[-1] == 'owner'
        sequence.append('callback')
        return original_callback(update, **kwargs)
    monkeypatch.setattr(repo, 'apply_guided_callback', apply)
    class Recovery:
        async def recover(self):
            assert repo.pending_orders() == repo.resumable_orders() == []
    class Checkout:
        async def run(self, order):
            pytest.fail('checkout must never execute')
    class IO:
        async def ack_callbacks(self): sequence.append('ack')
        async def send_pending(self): pass
        async def poll_once(self): raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.run(settings(tmp_path, conversation_engine='skills_agent',
            model_provider='ollama', guided_questions=flag), repo=repo, recovery=Recovery(),
            checkout=Checkout(), transport=IO()))
    assert repo.pending_events() == []
    reply = repo.event_result(1)[1]
    assert reply is not None
    if flag:
        assert 'guided_model' in sequence and 'agent_model' not in sequence
        assert sequence.index('ack') < sequence.index('callback')
    else:
        assert 'inactiv' in reply.text
        assert 'callback' not in sequence and 'guided_model' not in sequence
    assert repo.list_lines() == []


@pytest.mark.parametrize('engine', ['legacy', 'skills_agent'])
def test_flag_off_retained_real_callback_and_v2_never_enter_legacy_reduction(tmp_path, monkeypatch, engine):
    import runtime
    import shopping_agent.ollama
    from tests.guided_helpers import callback, message

    c = local_case(tmp_path)
    c.record_known_delivery()
    token = c.choice_token('one_each')
    c.repo.ingest_events([callback(2, token), message(3, '/lista'), message(4, 'sí')], 5)
    monkeypatch.setattr(shopping_agent.ollama, 'OllamaShoppingAgent', lambda model: object())
    class Recovery:
        async def recover(self): pass
    class Checkout:
        async def run(self, order): pytest.fail('checkout blocked')
    class IO:
        async def ack_callbacks(self): pass
        async def send_pending(self): pass
        async def poll_once(self): raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.run(settings(tmp_path, conversation_engine=engine,
            model_provider='ollama' if engine == 'skills_agent' else 'commands_only'),
            repo=c.repo, recovery=Recovery(), checkout=Checkout(), transport=IO()))
    assert 'inactiv' in c.repo.event_result(2)[1].text
    assert c.repo.guided_state(4, now=c.now).snapshot.proposal is None
    assert c.repo.list_lines() == []
    assert c.repo.pending_events() == []


def test_runtime_ack_precedes_actual_http_model_turn(tmp_path, monkeypatch):
    import httpx

    import runtime
    import shopping_agent.guided_ollama
    from tests.guided_helpers import PurchaseBlockedRepository, guided_http_response, message

    repo = PurchaseBlockedRepository(tmp_path / 'private' / 'guided.db')
    repo.migrate()
    repo.ingest_events([message(1, 'leche')], 2)
    sequence = []
    original_model = shopping_agent.guided_ollama.GuidedOllamaAgent
    def respond(request):
        assert sequence == ['recover', 'ack']
        sequence.append('model')
        return guided_http_response('milk')
    monkeypatch.setattr(shopping_agent.guided_ollama, 'GuidedOllamaAgent',
        lambda name: original_model(name, transport=httpx.MockTransport(respond)))
    class Recovery:
        async def recover(self): sequence.append('recover')
    class Checkout:
        async def run(self, order): pytest.fail('checkout blocked')
    class IO:
        async def ack_callbacks(self): sequence.append('ack')
        async def send_pending(self): pass
        async def poll_once(self): raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.run(settings(tmp_path, guided_questions=True, conversation_engine='skills_agent',
            model_provider='ollama'), repo=repo, recovery=Recovery(), checkout=Checkout(), transport=IO()))
    assert sequence == ['recover', 'ack', 'model']
    assert repo.guided_state(1, now=datetime.now(UTC)).question.kind == 'quantity_single'
    assert repo.pending_orders() == repo.resumable_orders() == []


@pytest.mark.parametrize('event_kind', ['message', 'callback'])
def test_owner_gate_rejects_foreign_durable_event_before_ack_dispatch(tmp_path, event_kind):
    import runtime
    from tests.guided_helpers import PurchaseBlockedRepository, callback, message

    repo = PurchaseBlockedRepository(tmp_path / 'private' / 'guided.db')
    repo.migrate()
    event = message(1, '/lista', owner=8) if event_kind == 'message' else callback(1, VALID_TOKEN, owner=8)
    repo.ingest_events([event], 2)
    class Recovery:
        async def recover(self): pytest.fail('foreign owner must fail before recovery')
    class Checkout:
        async def run(self, order): pytest.fail('checkout blocked')
    class IO:
        async def ack_callbacks(self): pytest.fail('foreign owner must fail before ack')
        async def send_pending(self): pytest.fail('foreign owner must fail before send')
        async def poll_once(self): pytest.fail('foreign owner must fail before poll')
    with pytest.raises((PermissionError, ValueError)):
        asyncio.run(runtime.run(settings(tmp_path, guided_questions=True,
            conversation_engine='skills_agent', model_provider='ollama'),
            repo=repo, recovery=Recovery(), checkout=Checkout(), transport=IO()))
    assert repo.event_result(1)[1] is None
