import asyncio
import json

import pytest

from domain import Reply
from storage import Repository
from tests.guided_helpers import callback, persisted_case
from tests.test_guided_conversation import Session


def consume_cancel(c):
    c.record_known_delivery()
    one = c.choice_token('one_each')
    c.ingest_callback(2, one)
    result = c.repo.apply_guided_callback(2, now=c.now)
    c.record_known_delivery(message_id=101)
    cancel = c.choice_token('cancel')
    c.ingest_callback(3, cancel, message_id=101)
    c.repo.apply_guided_callback(3, now=c.now)
    return one, result, cancel


@pytest.mark.parametrize('replays', [1, 3])
def test_callback_cancel_is_durable_boundary_for_cancelled_origin_replays(tmp_path, replays):
    c = persisted_case(tmp_path)
    with c.repo._connection(write=True) as db:
        db.execute("INSERT INTO list_lines VALUES ('saved',NULL,'leche',2,4,1)")
    saved = c.repo.list_lines()
    one, result, _ = consume_cancel(c)
    with c.repo._connection() as db:
        audit = [tuple(row) for row in db.execute('SELECT * FROM inbox WHERE update_id<=3')]
        notices = [tuple(row) for row in db.execute('SELECT * FROM outbox WHERE update_id<=3')]
    for update in range(4, 4 + replays):
        c.ingest_callback(update, one)
        assert c.repo.apply_guided_callback(update, now=c.now) == result
    assert Repository(c.repo.path).guided_history(7, 7) == ()
    assert c.repo.list_lines() == saved
    with c.repo._connection() as db:
        assert [tuple(row) for row in db.execute('SELECT * FROM inbox WHERE update_id<=3')] == audit
        assert [tuple(row) for row in db.execute('SELECT * FROM outbox WHERE update_id<=3')] == notices


def test_old_cancel_replay_cannot_erase_fresh_context(tmp_path):
    c = persisted_case(tmp_path)
    _, _, cancel = consume_cancel(c)
    c.ingest_message(4, 'leche fresca')
    c.repo.complete_agent_reply(4, Reply(text='contexto nuevo'))
    c.ingest_callback(5, cancel, message_id=101)
    c.repo.apply_guided_callback(5, now=c.now)
    assert Repository(c.repo.path).guided_history(7, 7) == (
        {'role': 'user', 'content': 'leche fresca'},
        {'role': 'assistant', 'content': 'contexto nuevo'},
    )


def test_callback_cancel_boundary_does_not_launder_corrupt_cancelled_origin_replay(tmp_path):
    c = persisted_case(tmp_path)
    one, result, _ = consume_cancel(c)
    c.ingest_callback(4, one)
    assert c.repo.apply_guided_callback(4, now=c.now) == result
    with c.repo._connection(write=True) as db:
        db.execute('UPDATE guided_tokens SET result_json=? WHERE token=?', ('{"text":"forged"}', one))
    with pytest.raises(ValueError):
        Repository(c.repo.path).guided_history(7, 7)


def test_unknown_callback_with_cancellation_wording_has_no_reset_authority(tmp_path):
    c = persisted_case(tmp_path)
    c.ingest_callback(2, 'q:' + 'Z' * 22)
    c.repo.complete_agent_reply(2, Reply(text='Propuesta cancelada. La lista no ha cambiado.'))
    with pytest.raises(ValueError):
        c.repo.guided_history(7, 7)


@pytest.mark.parametrize('damage', ['result', 'outbox', 'token', 'receipt', 'rejected'])
def test_corrupt_cancel_chain_cannot_grant_boundary_or_launder_old_replay(tmp_path, damage):
    c = persisted_case(tmp_path)
    one, result, cancel = consume_cancel(c)
    c.ingest_callback(4, one)
    assert c.repo.apply_guided_callback(4, now=c.now) == result
    with c.repo._connection(write=True) as db:
        if damage == 'result':
            db.execute('UPDATE guided_tokens SET result_json=? WHERE token=?', ('{"text":"forged"}', cancel))
        elif damage == 'outbox':
            db.execute('UPDATE outbox SET reply_json=? WHERE update_id=3', ('{"text":"forged"}',))
        elif damage == 'token':
            db.execute('UPDATE guided_tokens SET choice_index=0 WHERE token=?', (cancel,))
        elif damage == 'receipt':
            db.execute('DELETE FROM telegram_deliveries WHERE message_id=101')
        else:
            rejected = Reply(text='Pregunta anterior o entrega desconocida. Responde a la pregunta vigente.').model_dump_json()
            db.execute('UPDATE inbox SET reply_json=? WHERE update_id=3', (rejected,))
            db.execute('UPDATE outbox SET reply_json=? WHERE update_id=3', (rejected,))
            db.execute('UPDATE guided_tokens SET result_json=? WHERE token=?', (rejected, cancel))
    with pytest.raises(ValueError):
        Repository(c.repo.path).guided_history(7, 7)


@pytest.mark.parametrize('kind', ['unknown', 'missing_receipt', 'wrong_receipt', 'owner'])
def test_unauthenticated_cancel_never_resets_history(tmp_path, kind):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    if kind != 'missing_receipt':
        c.record_known_delivery()
    token = c.choice_token('cancel') if kind != 'unknown' else 'q:' + 'Z' * 22
    event = callback(2, token, message_id=999 if kind == 'wrong_receipt' else 100)
    if kind == 'owner':
        event = event.model_copy(update={'user_id': 8, 'chat_id': 8})
    c.repo.ingest_events([event], 3)
    c.repo.apply_guided_callback(2, now=c.now)
    assert c.repo.guided_history(7, 7)[0]['content'] == 'huevos carne atun'
    assert c.repo.list_lines() == []


@pytest.mark.parametrize('control', ['no', 'callback'])
def test_keep_topic_is_not_global_history_reset(tmp_path, control):
    s = Session(tmp_path)
    s.propose(['huevos', 'carne', 'atun'])
    offer = s.new_topic('leche')
    if control == 'no':
        s.send('no')
    else:
        s.number += 1
        token = next(b.token for row in offer.keyboard.rows for b in row if b.label == 'Mantener sin añadir')
        event = callback(s.number, token, message_id=2)
        s.repo.ingest_events([event], s.number + 1)
        asyncio.run(s.conversation.handle(event, 'dry_run'))
    assert s.repo.guided_history(7, 7)[0]['content'] == 'huevos, carne, atun'
    assert s.pending_names() == ['huevos', 'carne', 'atun']
    assert s.saved() == []


def test_conversation_http_context_excludes_cancelled_origin_and_fresh_request_progresses(tmp_path):
    s = Session(tmp_path)
    s.propose(['leche'], quantity=1)
    s.send('sí')
    saved = s.saved()
    offer = s.propose(['huevos', 'carne', 'atun'])
    one = next(b.token for row in offer.keyboard.rows for b in row if b.label == 'Uno de cada')

    def click(token, message_id):
        s.number += 1
        event = callback(s.number, token, message_id=message_id, query_id=f'query-{s.number}')
        s.repo.ingest_events([event], s.number + 1)
        reply = asyncio.run(s.conversation.handle(event, 'dry_run'))
        s.repo.mark_callback_ack(event.callback_query_id)
        asyncio.run(s.io.send_pending())
        return reply

    review = click(one, 3)
    cancel = next(b.token for row in review.keyboard.rows for b in row if b.label == 'Cancelar')
    click(cancel, 4)
    for _ in range(3):
        click(one, 3)
    s.send('2', 'clarify')
    request = json.loads(s.calls[-1].content)
    assert all(name not in json.dumps(request['messages'][1:]) for name in ('huevos', 'carne', 'atun'))
    assert s.state().snapshot.proposal is None
    assert s.saved() == saved
    s.propose(['arroz'], quantity=2)
    click(cancel, 4)
    assert 'arroz' in json.dumps(s.repo.guided_history(7, 7))
    assert s.pending_names() == ['arroz']
    s.send('sí')
    assert [(r.description, r.quantity) for r in s.saved()] == [('leche', 1), ('arroz', 2)]
