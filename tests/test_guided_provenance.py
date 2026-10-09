import json

import pytest

from shopping_agent.contracts import ItemInput, ProposeAdds
from shopping_agent.guided_contracts import TopicCandidate
from tests.guided_helpers import callback, persisted_case


def test_append_preserves_original_sources_and_revokes_old_review(tmp_path):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    c.record_known_delivery()
    old_token = c.choice_token('confirm')
    original = c.repo.guided_state(1, now=c.now).snapshot.proposal
    c.ingest_message(2, 'también leche')
    c.repo.apply_guided(2, TopicCandidate(source_update_id=2,
        adds=ProposeAdds(items=(ItemInput(description='leche', quantity=2),))),
        expected_question_version=c.question().version, now=c.now)
    c.ingest_message(3, 'sí')
    c.repo.apply_guided(3, None, expected_question_version=c.question().version, now=c.now)
    proposal = c.repo.guided_state(3, now=c.now).snapshot.proposal
    assert proposal.id == original.id
    assert proposal.original_text == original.original_text
    assert proposal.items[:3] == original.items
    assert [(p.update_id, p.kind) for p in proposal.contributions][-2:] == [(2, 'append'), (3, 'decision')]
    assert c.repo.event_result(2)[0].text == 'también leche'
    c.ingest_callback(4, old_token)
    c.repo.apply_guided_callback(4, now=c.now)
    assert c.repo.list_lines() == []


def test_history_last_three_owner_pairs_without_callback_secrets(tmp_path):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    c.ingest_callback(2, c.choice_token('one_each'), query_id='private-query')
    c.repo.apply_guided_callback(2, now=c.now)
    for i in range(3, 6):
        c.ingest_message(i, f'consulta-{i}')
        c.repo.apply_guided(i, None, expected_question_version=c.question().version, now=c.now)
    history = c.repo.guided_history(7, 7)
    assert len(history) == 6
    assert history[0] == {'role': 'user', 'content': 'consulta-3'}
    assert c.repo.guided_history(8, 8) == ()
    assert 'q:' not in json.dumps(history)
    assert 'private-query' not in json.dumps(history)


def test_callback_history_translates_only_valid_choice_and_replay_conflicts(tmp_path):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    token = c.choice_token('one_each')
    c.ingest_callback(2, token, query_id='private-query')
    c.repo.apply_guided_callback(2, now=c.now)
    history = c.repo.guided_history(7, 7)
    assert history[-2] == {'role': 'user', 'content': 'Uno de cada'}
    assert token not in json.dumps(history)
    with pytest.raises(ValueError, match='Conflicting callback query'):
        c.repo.ingest_events([callback(3, token, query_id='private-query', message_id=101)], 4)


def test_revoke_removes_pending_not_saved_rows(tmp_path):
    c = persisted_case(tmp_path)
    c.repo.revoke_guided(7, now=c.now)
    state = c.repo.guided_state(1, now=c.now)
    assert state.snapshot.proposal is None
    assert state.question is None
    assert c.repo.list_lines() == []


def test_delivery_hook_is_atomic_even_for_idempotent_receipt(tmp_path, monkeypatch):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    c.record_known_delivery()
    with c.repo._connection(write=True) as db:
        row = db.execute('SELECT proposal_json FROM agent_proposals').fetchone()
        payload = json.loads(row[0])
        payload['review']['delivered_message_id'] = None
        db.execute('UPDATE agent_proposals SET proposal_json=?', (json.dumps(payload),))
    assert c.repo.guided_state(1, now=c.now).review.delivered_message_id is None
    original = c.repo._write_agent_proposal

    def fail(*args):
        original(*args)
        raise RuntimeError('delivery-failpoint')

    with monkeypatch.context() as patch:
        patch.setattr(c.repo, '_write_agent_proposal', fail)
        with pytest.raises(RuntimeError, match='delivery-failpoint'):
            c.record_known_delivery()
    assert c.repo.guided_state(1, now=c.now).review.delivered_message_id is None
    c.record_known_delivery()
    assert c.repo.guided_state(1, now=c.now).review.delivered_message_id == 100


def test_delivery_mismatched_digest_and_expired_review_never_grants_witness(tmp_path, monkeypatch):
    from datetime import datetime, timedelta

    from shopping_agent import guided_storage

    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    with c.repo._connection() as db:
        notice = db.execute('SELECT notice_id FROM guided_questions').fetchone()[0]
    c.repo.record_delivery(notice, 7, 100, 'wrong-full-summary-digest')
    assert c.repo.guided_state(1, now=c.now).review.delivered_message_id is None

    class ExpiredClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return c.now + timedelta(minutes=16)

    monkeypatch.setattr(guided_storage, 'datetime', ExpiredClock)
    c.record_known_delivery(message_id=101)
    assert c.repo.guided_state(1, now=c.now).review.delivered_message_id is None


@pytest.mark.parametrize('damage', ['token', 'source', 'notice', 'digest', 'contribution'])
def test_invalid_retained_state_fails_closed(tmp_path, damage):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    with c.repo._connection(write=True) as db:
        if damage == 'token':
            db.execute('UPDATE guided_tokens SET choice_index=19')
        elif damage == 'source':
            db.execute("UPDATE inbox SET text='changed original',payload_json=NULL WHERE update_id=1")
        elif damage == 'notice':
            db.execute('UPDATE outbox SET reply_json=?', ('{"text":"wrong full summary","order_id":null}',))
        else:
            payload = json.loads(db.execute('SELECT proposal_json FROM agent_proposals').fetchone()[0])
            if damage == 'digest':
                payload['review']['summary_digest'] = 'forged'
            else:
                payload['contributions'][0]['update_id'] = 99
            db.execute('UPDATE agent_proposals SET proposal_json=?', (json.dumps(payload),))
    assert c.repo.guided_state(1, now=c.now).snapshot.proposal is None
    with pytest.raises(PermissionError):
        c.repo.assert_authorized_owner(7)


def test_corrupt_history_never_becomes_model_context(tmp_path):
    c = persisted_case(tmp_path)
    with c.repo._connection(write=True) as db:
        db.execute('UPDATE inbox SET reply_json=?', ('{"text":"forged","order_id":null}',))
    with pytest.raises(ValueError, match='History'):
        c.repo.guided_history(7, 7)


def test_revoke_keeps_authenticated_history_and_blocks_old_choice(tmp_path):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    token = c.choice_token('one_each')
    c.ingest_callback(2, token)
    c.repo.apply_guided_callback(2, now=c.now)
    history = c.repo.guided_history(7, 7)
    pending = c.choice_token('confirm')
    c.repo.revoke_guided(7, now=c.now)
    assert c.repo.guided_history(7, 7) == history
    c.ingest_callback(3, pending)
    c.repo.apply_guided_callback(3, now=c.now)
    assert not c.repo.list_lines()
    c.repo.assert_authorized_owner(7)


@pytest.mark.parametrize('switch', ['route', 'local'])
def test_mode_switch_revokes_questions_and_warns_without_changing_lines(tmp_path, caplog, switch):
    c = persisted_case(tmp_path)
    q = c.question()
    with caplog.at_level('WARNING', logger='runtime'):
        if switch == 'route':
            c.repo.set_conversation_route(7, 7, 'legacy', now=c.now)
        else:
            c.repo.revoke_agent_proposals()
    assert 'discard' in caplog.text.lower()
    with c.repo._connection() as db:
        payload = db.execute('SELECT question_json FROM guided_questions WHERE id=?', (str(q.id),)).fetchone()[0]
    assert json.loads(payload)['status'] == 'revoked'
    assert c.repo.agent_snapshot(1, now=c.now).proposal is None
    assert not c.repo.list_lines()
    c.repo.assert_authorized_owner(7)


def test_expired_legacy_command_query_after_guided_revoke_does_not_poison_owner_check(tmp_path):
    import asyncio
    from datetime import timedelta

    from conversation import Conversation
    from runtime import _CommandsOnly
    from tests.guided_helpers import message

    c = persisted_case(tmp_path)
    c.repo.revoke_guided(7, now=c.now)
    handler = Conversation(c.repo, _CommandsOnly(), clock=lambda: c.now)
    c.ingest_message(2, '/anadir arroz')
    asyncio.run(handler.handle(message(2, '/anadir arroz'), 'dry_run'))
    with c.repo._connection() as db:
        assert db.execute('SELECT command_update_id FROM conversation_routes').fetchone()[0] == 2
    c.ingest_message(3, '/lista')
    handler = Conversation(c.repo, _CommandsOnly(), clock=lambda: c.now + timedelta(minutes=16))
    asyncio.run(handler.handle(message(3, '/lista'), 'dry_run'))
    c.repo.assert_authorized_owner(7)
    assert c.repo.command_origin(7, 7) is None
    c.ingest_message(4, '/lista')
    assert asyncio.run(handler.handle(message(4, '/lista'), 'dry_run')).text


def test_v1_proposal_transitions_without_weakening_original_validation(tmp_path):
    from storage import Repository
    from tests.guided_helpers import NOW, message

    repo = Repository(tmp_path / 'v1.db')
    repo.migrate()
    repo.ingest_batch([message(1, 'huevos carne atun')], 2)
    repo.apply_agent_operation(1, 'proponer_altas', {'items': [
        {'description': 'huevos'}, {'description': 'carne'}, {'description': 'atun'}]}, None, now=NOW)
    assert repo.agent_snapshot(1, now=NOW).proposal.schema_version == 1
    repo.ingest_batch([message(2, 'revisar')], 3)
    repo.apply_guided(2, None, expected_question_version=None, now=NOW)
    q = repo.guided_state(2, now=NOW).question
    repo.ingest_batch([message(3, 'Uno de cada')], 4)
    repo.apply_guided(3, None, expected_question_version=q.version, now=NOW)
    assert repo.agent_snapshot(3, now=NOW).proposal.schema_version == 2
    with repo._connection(write=True) as db:
        db.execute("UPDATE inbox SET text='/comprar',payload_json=NULL WHERE update_id=1")
    assert repo.agent_snapshot(3, now=NOW).proposal is None


def test_pending_topic_source_text_is_validated_during_owner_recovery(tmp_path):
    c = persisted_case(tmp_path)
    c.ingest_message(2, 'leche')
    c.repo.apply_guided(2, TopicCandidate(source_update_id=2,
        adds=ProposeAdds(items=(ItemInput(description='leche'),))),
        expected_question_version=c.question().version, now=c.now)
    with c.repo._connection(write=True) as db:
        payload = json.loads(db.execute('SELECT topic_json FROM guided_topics').fetchone()[0])
        payload['original_text'] = 'different-source'
        db.execute('UPDATE guided_topics SET topic_json=?', (json.dumps(payload),))
    assert c.repo.guided_state(2, now=c.now).snapshot.proposal is None
    with pytest.raises(PermissionError):
        c.repo.assert_authorized_owner(7)
