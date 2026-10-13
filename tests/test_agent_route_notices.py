"""Durable user-visible notices are separate from committed reply witnesses."""

import sqlite3

import pytest

from domain import Reply
from storage import Repository
from tests.test_agent_storage import NOW, ingest, propose


@pytest.fixture
def repo(tmp_path):
    result = Repository(tmp_path / 'agent.db')
    result.migrate()
    result.set_conversation_route(7, 7, 'agent', now=NOW)
    return result


def notices(repo):
    with repo._connection() as db:
        return [dict(row) for row in db.execute('SELECT * FROM outbox WHERE update_id IS NULL')]


def test_discard_queues_standalone_notice_without_rewriting_review_or_saved_rows(repo):
    from tests.dialogue_support import seed_line
    seed_line(repo, 'pan', 2)
    propose(repo, update=2)
    lines = repo.list_lines()
    original = repo.message_result(2)
    with repo._connection() as db:
        review = dict(db.execute('SELECT * FROM outbox WHERE update_id=2').fetchone())
    assert repo.set_conversation_route(7, 7, 'legacy', now=NOW)
    queued = notices(repo)
    assert len(queued) == 1
    assert queued[0]['chat_id'] == 7 and queued[0]['sent_at'] is None
    reply = Reply.model_validate_json(queued[0]['reply_json'])
    assert 'contexto anterior' in reply.text
    assert 'formular' in reply.text
    assert 'guardadas no han cambiado' in reply.text
    assert reply.order_id is None
    assert (queued[0]['id'], 7, reply.text) in repo.pending_notices()
    assert repo.message_result(2) == original
    assert repo.list_lines() == lines
    assert repo.agent_snapshot(2, now=NOW).proposal is None
    with repo._connection() as db:
        assert dict(db.execute('SELECT * FROM outbox WHERE update_id=2').fetchone()) == review
    repo.assert_authorized_owner(7)


def test_notice_survives_restart_and_same_route_replay_does_not_duplicate(repo):
    propose(repo)
    repo.set_conversation_route(7, 7, 'legacy', now=NOW)
    queued = notices(repo)
    restarted = Repository(repo.path)
    restarted.migrate()
    assert notices(restarted) == queued
    assert not restarted.set_conversation_route(7, 7, 'legacy', now=NOW)
    assert notices(restarted) == queued
    restarted.mark_notice_sent(queued[0]['id'])
    assert not restarted.set_conversation_route(7, 7, 'legacy', now=NOW)
    assert len(notices(restarted)) == 1
    assert all(item[0] != queued[0]['id'] for item in restarted.pending_notices())
    # Returning to agent with no remaining incompatible memory is not a discard.
    restarted.set_conversation_route(7, 7, 'agent', now=NOW)
    assert len(notices(restarted)) == 1


def test_notice_failure_rolls_back_route_and_permission_invalidation(repo):
    propose(repo)
    before = repo.agent_snapshot(1, now=NOW).proposal
    with repo._connection(write=True) as db:
        db.execute("CREATE TRIGGER reject_discard_notice BEFORE INSERT ON outbox "
                   "WHEN NEW.update_id IS NULL BEGIN SELECT RAISE(ABORT,'failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        repo.set_conversation_route(7, 7, 'legacy', now=NOW)
    assert repo.agent_snapshot(1, now=NOW).proposal == before
    assert not notices(repo)
    with repo._connection(write=True) as db:
        assert db.execute('SELECT route FROM conversation_routes').fetchone()[0] == 'agent'
        db.execute('DROP TRIGGER reject_discard_notice')
    assert repo.set_conversation_route(7, 7, 'legacy', now=NOW)
    assert len(notices(repo)) == 1


def test_preserved_genuine_slash_continuation_emits_no_discard_notice(repo):
    from interpreter import parse_command
    repo.set_conversation_route(7, 7, 'legacy', now=NOW)
    ingest(repo, 1, '/anadir arroz')
    repo.apply_dialogue(1, parse_command('/anadir arroz', []), 'dry_run', now=NOW)
    before = repo.dialogue_state(7, 7, now=NOW)
    assert repo.set_conversation_route(7, 7, 'agent', now=NOW)
    assert repo.command_origin(7, 7).update_id == 1
    assert repo.dialogue_state(7, 7, now=NOW) == before
    assert not notices(repo)


@pytest.mark.parametrize('user,chat', [(7, 8), (0, 0), (-7, -7), (True, True)])
def test_invalid_private_route_identity_cannot_discard_or_enqueue(repo, user, chat):
    propose(repo)
    before = repo.agent_snapshot(1, now=NOW).proposal
    with pytest.raises(ValueError):
        repo.set_conversation_route(user, chat, 'legacy', now=NOW)
    assert not notices(repo)
    assert repo.agent_snapshot(1, now=NOW).proposal == before


def test_notice_recipient_comes_from_route_key_not_untrusted_proposal_payload(repo):
    import json
    propose(repo)
    with repo._connection(write=True) as db:
        payload = json.loads(db.execute('SELECT proposal_json FROM agent_proposals').fetchone()[0])
        payload['chat_id'] = 8
        db.execute('UPDATE agent_proposals SET proposal_json=?', (json.dumps(payload),))
    repo.set_conversation_route(7, 7, 'legacy', now=NOW)
    assert [row['chat_id'] for row in notices(repo)] == [7]
    repo.assert_authorized_owner(7)
