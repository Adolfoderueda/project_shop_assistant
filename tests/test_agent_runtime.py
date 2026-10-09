import asyncio
from datetime import UTC, datetime

import pytest

import cli
from config import Settings, load_settings, save_settings
from domain import IncomingMessage
from runtime import ProcessLock
from storage import Repository

NOW = datetime(2026, 10, 8, tzinfo=UTC)


def configured(tmp_path):
    settings = Settings(telegram_token='secret-token', authorized_user_id=7, address='secret-address',
                        database_path=tmp_path / 'private' / 'assistant.db')
    save_settings(tmp_path, settings)
    repo = Repository(settings.database_path)
    repo.migrate()
    return repo


def proposal(repo):
    repo.ingest_batch([IncomingMessage(update_id=1, user_id=7, chat_id=7, text='arroz')], 2)
    repo.apply_agent_operation(1, 'proponer_altas', {'items': [{'description': 'arroz', 'quantity': 2}]}, None, now=NOW)


def test_runtime_default_remains_legacy(tmp_path):
    configured(tmp_path)
    assert load_settings(tmp_path).conversation_engine == 'legacy'
    with pytest.raises(ValueError):
        Settings(telegram_token='x', authorized_user_id=7, address='x', conversation_engine='skills_agent')


def test_configuration_lock_and_secret_safety(tmp_path, monkeypatch, capsys):
    repo = configured(tmp_path)
    async def available(model):
        assert model == 'gemma4:e4b-it-q4_K_M'
        return True
    monkeypatch.setattr(cli, 'ollama_available', available)
    with ProcessLock(repo.path.parent / 'worker.lock'):
        assert not asyncio.run(cli.agent_local(tmp_path, 'enable'))
    assert asyncio.run(cli.agent_local(tmp_path, 'enable'))
    settings = load_settings(tmp_path)
    assert settings.conversation_engine == 'skills_agent'
    assert settings.ollama_model == 'gemma4:e2b'
    proposal(repo)
    assert asyncio.run(cli.agent_local(tmp_path, 'status'))
    assert repo.agent_snapshot(1, now=NOW).proposal is not None
    assert asyncio.run(cli.agent_local(tmp_path, 'disable'))
    assert repo.agent_snapshot(1, now=NOW).proposal is None
    assert 'secret' not in capsys.readouterr().out


def test_model_local_disable_from_agent_is_valid_and_revokes_permission(tmp_path, monkeypatch):
    repo = configured(tmp_path)
    settings = load_settings(tmp_path).model_copy(update={'model_provider': 'ollama', 'conversation_engine': 'skills_agent'})
    save_settings(tmp_path, settings)
    proposal(repo)
    assert asyncio.run(cli.model_local(tmp_path, 'disable'))
    settings = load_settings(tmp_path)
    assert (settings.model_provider, settings.conversation_engine) == ('commands_only', 'legacy')
    assert repo.agent_snapshot(1, now=NOW).proposal is None


def test_failed_save_cannot_restore_permission(tmp_path, monkeypatch):
    repo = configured(tmp_path)
    proposal(repo)
    monkeypatch.setattr(cli, 'save_settings', lambda *a: (_ for _ in ()).throw(OSError('failed')))
    with pytest.raises(OSError):
        asyncio.run(cli.agent_local(tmp_path, 'disable'))
    assert repo.agent_snapshot(1, now=NOW).proposal is None


@pytest.mark.parametrize('engine', ['legacy', 'skills_agent'])
def test_runtime_constructs_only_selected_engine(tmp_path, monkeypatch, engine):
    import conversation
    import ollama_replies
    import runtime
    import shopping_agent.conversation
    import shopping_agent.ollama

    repo = configured(tmp_path)
    settings = load_settings(tmp_path).model_copy(update={
        'conversation_engine': engine, 'model_provider': 'ollama'})
    constructed = []
    original = conversation.Conversation

    def legacy(*args, **kwargs):
        constructed.append(('legacy', kwargs))
        return original(*args, **kwargs)

    def writer(model):
        constructed.append(('writer', model))

    def agent(model):
        constructed.append(('agent', model))
        return object()

    monkeypatch.setattr(conversation, 'Conversation', legacy)
    monkeypatch.setattr(ollama_replies, 'OllamaReplyWriter', writer)
    monkeypatch.setattr(shopping_agent.ollama, 'OllamaShoppingAgent', agent)

    class Recovery:
        async def recover(self): pass

    class IO:
        async def ack_callbacks(self): pass
        async def send_pending(self): pass
        async def poll_once(self): raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.run(settings, repo=repo, recovery=Recovery(), checkout=object(), transport=IO()))
    names = [entry[0] for entry in constructed]
    if engine == 'skills_agent':
        assert names == ['agent', 'legacy']
        assert constructed[0][1] == 'gemma4:e4b-it-q4_K_M'
    else:
        assert names == ['writer', 'legacy']
        assert constructed[-1][1]['synchronize_route'] is True


def test_agent_status_is_read_only_even_while_worker_locked(tmp_path, monkeypatch):
    repo = configured(tmp_path)
    proposal(repo)
    target = tmp_path / 'private' / 'settings.json'
    before = target.read_bytes()
    monkeypatch.chdir(tmp_path)
    with ProcessLock(repo.path.parent / 'worker.lock'):
        assert cli.main(['agent-local', 'status']) == 0
    assert target.read_bytes() == before
    assert repo.agent_snapshot(1, now=NOW).proposal is not None
