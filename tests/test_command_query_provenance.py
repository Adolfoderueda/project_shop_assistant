"""Queries must not orphan command permission when dialogue memory is discarded."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from conversation import Conversation
from domain import IncomingMessage, Intent, IntentLine
from runtime import _CommandsOnly
from shopping_agent.conversation import AgentConversation
from storage import Repository

NOW = datetime(2026, 10, 8, tzinfo=UTC)


class NoAgent:
    async def run(self, message, tools):
        pytest.fail('Explicit commands and their continuations must not call the model')


def conversation(repo, engine, clock):
    legacy = Conversation(repo, _CommandsOnly(), clock=clock)
    return (AgentConversation(repo, NoAgent(), legacy, clock=clock)
            if engine == 'agent' else legacy)


def send(repo, handler, update_id, text):
    message = IncomingMessage(update_id=update_id, user_id=7, chat_id=7, text=text)
    repo.ingest_batch([message], update_id + 1)
    return asyncio.run(handler.handle(message, 'dry_run'))


def command_link(repo):
    with repo._connection() as db:
        return db.execute('SELECT command_update_id FROM conversation_routes '
                          'WHERE user_id=7 AND chat_id=7').fetchone()[0]


@pytest.mark.parametrize('engine', ['legacy', 'agent'])
@pytest.mark.parametrize('invalidated', ['expired', 'deleted', 'revised', 'incompatible', 'finished'])
def test_read_only_query_clears_discarded_command_permission_after_restart(
    tmp_path, engine, invalidated,
):
    query = '/lista'
    repo = Repository(tmp_path / 'synthetic.db')
    repo.migrate()
    current = [NOW]
    handler = conversation(repo, engine, lambda: current[0])
    send(repo, handler, 1, '/anadir 1 arroz')
    send(repo, handler, 2, '/anadir arroz')
    assert command_link(repo) == 2
    repo.assert_authorized_owner(7)
    state = repo.dialogue_state(7, 7, now=NOW)
    if invalidated == 'expired':
        current[0] += timedelta(minutes=16)
    elif invalidated in {'deleted', 'revised'}:
        with repo._connection(write=True) as db:
            if invalidated == 'deleted':
                db.execute('DELETE FROM list_lines')
            else:
                db.execute('UPDATE list_lines SET revision=revision+1')
    else:
        # Valid owned memory, but no longer the continuation of command 2.
        repo.ingest_batch([IncomingMessage(update_id=3, user_id=7, chat_id=7,
                                          text='pan')], 4)
        replacement = (state.model_copy(update={'question': None}) if invalidated == 'finished'
                       else state.model_copy(update={'focus': state.focus.model_copy(update={
                           'description': 'pan', 'source_update_id': 3})}))
        with repo._connection(write=True) as db:
            repo._write_dialogue_state(db, replacement, 7, 7)

    # Reopen before the query, then again before owner validation/recovery.
    repo = Repository(repo.path)
    repo.migrate()
    handler = conversation(repo, engine, lambda: current[0])
    before = repo.list_lines()
    reply = send(repo, handler, 4, query)
    assert reply.text
    assert repo.list_lines() == before
    assert command_link(repo) is None
    reopened = Repository(repo.path)
    reopened.migrate()
    reopened.assert_authorized_owner(7)
    assert reopened.command_origin(7, 7) is None
    assert send(reopened, conversation(reopened, engine, lambda: current[0]), 4, query) == reply
    if invalidated in {'expired', 'deleted', 'revised'}:
        assert reopened.dialogue_state(7, 7, now=current[0]) is None


@pytest.mark.parametrize('engine', ['legacy', 'agent'])
def test_read_only_query_preserves_live_command_permission_and_ttl(tmp_path, engine):
    repo = Repository(tmp_path / 'synthetic.db')
    repo.migrate()
    handler = conversation(repo, engine, lambda: NOW)
    send(repo, handler, 1, '/anadir arroz')
    before = repo.dialogue_state(7, 7, now=NOW)
    later = NOW + timedelta(minutes=1)
    send(repo, conversation(repo, engine, lambda: later), 2, '/lista')
    reopened = Repository(repo.path)
    reopened.migrate()
    reopened.assert_authorized_owner(7)
    assert command_link(reopened) == 1
    assert reopened.dialogue_state(7, 7, now=later) == before
    send(reopened, conversation(reopened, engine, lambda: later), 3, '2')
    assert [(line.description, line.quantity) for line in reopened.list_lines()] == [('arroz', 2)]
    assert command_link(reopened) is None


@pytest.mark.parametrize('engine', ['legacy', 'agent'])
def test_query_provenance_cleanup_rolls_back_with_dialogue_transition(tmp_path, engine, monkeypatch):
    repo = Repository(tmp_path / 'synthetic.db')
    repo.migrate()
    send(repo, conversation(repo, engine, lambda: NOW), 1, '/anadir arroz')
    before = repo.dialogue_state(7, 7, now=NOW)

    def fail_completion(*args):
        assert command_link_in_transaction(args[0]) is None
        raise RuntimeError('injected completion failure')

    with monkeypatch.context() as patch:
        patch.setattr(repo, '_complete_reply', fail_completion)
        with pytest.raises(RuntimeError, match='injected completion failure'):
            send(repo, conversation(repo, engine, lambda: NOW + timedelta(minutes=16)), 2, '/lista')
    assert command_link(repo) == 1
    assert repo.dialogue_state(7, 7, now=NOW) == before
    assert repo.message_result(2)[1] is None
    repo.assert_authorized_owner(7)


def command_link_in_transaction(db):
    return db.execute('SELECT command_update_id FROM conversation_routes '
                      'WHERE user_id=7 AND chat_id=7').fetchone()[0]


@pytest.mark.parametrize('expired', [False, True])
def test_product_query_keeps_only_live_command_permission(tmp_path, expired):
    repo = Repository(tmp_path / 'synthetic.db')
    repo.migrate()
    send(repo, conversation(repo, 'legacy', lambda: NOW), 1, '/anadir arroz')
    before = repo.dialogue_state(7, 7, now=NOW)
    message = IncomingMessage(update_id=2, user_id=7, chat_id=7, text='¿Qué sabes de arroz?')
    repo.ingest_batch([message], 3)
    now = NOW + timedelta(minutes=16 if expired else 1)
    reply = repo.apply_dialogue(2, Intent(action='product_query', lines=[
        IntentLine(description='arroz')]), 'dry_run', now=now)
    assert reply.text
    reopened = Repository(repo.path)
    reopened.migrate()
    reopened.assert_authorized_owner(7)
    assert command_link(reopened) == (None if expired else 1)
    after = reopened.dialogue_state(7, 7, now=now)
    if expired:
        # The query may establish informational focus, never a continuation.
        assert after.question is None
        assert after.focus.source_update_id == 2
    else:
        assert after == before
    assert not reopened.list_lines()
