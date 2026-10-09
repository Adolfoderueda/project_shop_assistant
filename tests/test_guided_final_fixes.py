import asyncio
import json
from datetime import timedelta

import httpx
import pytest

from domain import Reply
from shopping_agent.contracts import ItemInput, ItemPatch, ProposeAdds
from shopping_agent.guided_contracts import QuantityCandidate, TopicCandidate
from shopping_agent.guided_replies import render_question, review_fits
from storage import Repository
from tests.guided_helpers import persisted_case
from tests.test_guided_conversation import Session


@pytest.mark.parametrize('kind', ['expired', 'unknown', 'copy', 'different', 'inactive'])
def test_rejected_callbacks_leave_last_three_eligible_history_pairs(tmp_path, kind):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    token = c.choice_token('same_quantity' if kind == 'different' else 'one_each')
    if kind == 'different':
        c.ingest_callback(2, c.choice_token('one_each'))
        c.repo.apply_guided_callback(2, now=c.now)
    for i in range(3, 6):
        c.ingest_message(i, f'consulta-{i}')
        c.repo.complete_agent_reply(i, Reply(text=f'resultado-{i}'))
    if kind == 'expired':
        c.now += timedelta(minutes=16)
    if kind == 'unknown':
        token = 'q:' + 'Z' * 22
    c.ingest_callback(6, token, message_id=999 if kind == 'copy' else 100)
    if kind == 'inactive':
        c.repo.revoke_guided(7, now=c.now)
        c.repo.complete_agent_reply(6, Reply(
            text='Preguntas guiadas inactivas. Usa la conversación actual.'))
    else:
        c.repo.apply_guided_callback(6, now=c.now)
    repo = Repository(c.repo.path)  # Durable classification survives restart.
    history = repo.guided_history(7, 7)
    assert [h['content'] for h in history[::2]] == ['consulta-3', 'consulta-4', 'consulta-5']
    assert 'q:' not in json.dumps(history)


@pytest.mark.parametrize('damage', ['result', 'consumed', 'token'])
def test_corrupted_successful_callback_is_never_excluded_as_rejection(tmp_path, damage):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    c.ingest_callback(2, c.choice_token('one_each'))
    c.repo.apply_guided_callback(2, now=c.now)
    with c.repo._connection(write=True) as db:
        if damage == 'result':
            db.execute("UPDATE guided_tokens SET result_json='{}' WHERE consumed_update_id=2")
        elif damage == 'consumed':
            db.execute('UPDATE guided_tokens SET consumed_update_id=NULL,result_json=NULL WHERE consumed_update_id=2')
        else:
            db.execute('DELETE FROM guided_tokens WHERE consumed_update_id=2')
    with pytest.raises(ValueError):
        c.repo.guided_history(7, 7)


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('answer', ['2', 'dos', 'leche una', 'Todos'])
def test_expired_recipient_requires_durable_reset_before_any_native_inference(tmp_path, legacy, answer):
    s = Session(tmp_path)
    if legacy:
        s.send('/anadir arroz')
    else:
        s.propose(['arroz', 'carne'])
    s.now += timedelta(minutes=16)
    before_calls = len(s.calls)
    s.responses.append(httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {
        'role': 'assistant', 'tool_calls': [{'function': {'name': 'proponer_altas',
            'arguments': {'items': [{'description': 'arroz', 'quantity': 2}]}}}]}}))
    reply = s.send(answer)
    assert reply.text == 'La petición anterior ha caducado. Cancélala para iniciar una nueva.'
    assert len(s.calls) == before_calls
    assert s.saved() == []
    s.responses.clear()
    s.send('Cancelar')
    assert s.repo.guided_history(7, 7) == ()
    s.new_topic('leche')
    assert s.pending_names() == ['leche']
    request = json.loads(s.calls[-1].content)
    assert len(request['messages']) == 3  # System plus current real input/context, no old pairs.
    assert 'arroz' not in json.dumps(request['messages'][1:])
    with s.repo._connection() as db:
        assert db.execute('SELECT count(*) FROM inbox').fetchone()[0] == 4


@pytest.mark.parametrize('earlier_question', [False, True])
def test_exact_cancel_after_expiry_discards_topic_and_review_not_saved_rows(tmp_path, earlier_question):
    s = Session(tmp_path)
    s.propose(['leche'], quantity=1)
    s.send('sí')
    saved = s.saved()
    s.propose(['carne'], quantity=2)
    s.new_topic('atun')
    if earlier_question:
        with s.repo._connection(write=True) as db:
            row = db.execute("SELECT id,question_json FROM guided_questions WHERE "
                "json_extract(question_json,'$.status')='active'").fetchone()
            q = json.loads(row['question_json'])
            q['expires_at'] = (s.now + timedelta(seconds=1)).isoformat()
            db.execute('UPDATE guided_questions SET question_json=? WHERE id=?', (json.dumps(q), row['id']))
        s.now += timedelta(seconds=2)
    else:
        s.now += timedelta(minutes=16)
    s.send('Cancelar')
    assert s.state().snapshot.proposal is s.state().topic is s.state().question is None
    assert s.saved() == saved


def test_clock_refresh_rejects_quantity_crossing_expiry_during_http(tmp_path):
    s = Session(tmp_path)
    s.propose(['leche'])
    before = s.state().snapshot.proposal

    def slow(request):
        s.now += timedelta(minutes=16)
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {
            'role': 'assistant', 'tool_calls': [{'function': {'name': 'responder_cantidad',
                'arguments': {'quantity': 2}}}]}})

    s.agent.transport = httpx.MockTransport(slow)
    reply = s.send('dos')
    assert 'caducado' in reply.text
    assert s.state().snapshot.proposal == before
    assert s.saved() == []


@pytest.mark.parametrize('astral', [False, True])
def test_oversized_scope_keeps_full_candidate_and_facts_without_tokens(tmp_path, astral):
    s = Session(tmp_path)
    names = [f'{i:02} ' + ('😀' if astral else 'x') * 157 for i in range(20)]
    from tests.guided_helpers import message
    s.number = 1
    s.repo.ingest_events([message(1, ', '.join(names))], 2)
    s.repo.apply_guided(1, TopicCandidate(source_update_id=1,
        adds=ProposeAdds(items=tuple(ItemInput(description=name) for name in names))),
        expected_question_version=None, now=s.now)
    asyncio.run(s.io.send_pending())
    s.number += 1
    s.repo.ingest_events([message(s.number, 'dos')], s.number + 1)
    reply = s.repo.apply_guided(s.number, QuantityCandidate(source_update_id=s.number,
        patches=(ItemPatch(position=1, quantity=2),)),
        expected_question_version=s.state().question.version, now=s.now)
    asyncio.run(s.io.send_pending())
    state = s.state()
    assert not review_fits(render_question(state.question))
    assert state.question.candidate.patches[0].quantity == 2
    assert [i.description for i in state.snapshot.proposal.items] == names
    assert reply.keyboard is None and review_fits(reply)
    assert 'dividir' in reply.text
    with s.repo._connection() as db:
        assert db.execute('SELECT count(*) FROM guided_tokens WHERE question_id=?',
                          (str(state.question.id),)).fetchone()[0] == 0
    s.repo.assert_authorized_owner(7)


def test_repository_rejects_stale_topic_candidate_without_silent_reset(tmp_path):
    c = persisted_case(tmp_path)
    c.ingest_message(2, '2')
    before = c.repo.guided_state(2, now=c.now)
    reply = c.repo.apply_guided(2, TopicCandidate(source_update_id=2,
        adds=ProposeAdds(items=(ItemInput(description='arroz', quantity=2),))),
        expected_question_version=before.question.version, now=c.now + timedelta(minutes=16))
    assert 'Cancélala' in reply.text
    assert c.repo.guided_state(2, now=c.now).snapshot.proposal == before.snapshot.proposal


def test_pure_controller_returns_deliverable_split_request_for_long_topic():
    from shopping_agent.guided_controller import reduce_guided
    from tests.guided_helpers import NOW, message, state_fixture
    text = 'también ' + 'leche ' * 800
    decision = reduce_guided(state_fixture(), message(2, text), TopicCandidate(source_update_id=2,
        adds=ProposeAdds(items=(ItemInput(description='leche'),))), now=NOW)
    assert decision.state.topic.original_text == text
    assert decision.state.question.kind == 'topic'
    assert not review_fits(render_question(decision.state.question))
    assert review_fits(decision.reply) and decision.reply.keyboard is None
    assert 'dividir' in decision.reply.text


def test_expired_reset_is_atomic_and_durable_with_rejected_callback(tmp_path, monkeypatch):
    s = Session(tmp_path)
    reply = s.propose(['arroz'], quantity=2)
    from tests.guided_helpers import callback, message
    s.now += timedelta(minutes=16)
    s.number = 2
    event = callback(2, reply.keyboard.rows[0][0].token, message_id=1)
    s.repo.ingest_events([event], 3)
    asyncio.run(s.conversation.handle(event, 'dry_run'))
    s.repo.mark_callback_ack(event.callback_query_id)
    assert s.repo.guided_history(7, 7)[0]['content'] == 'arroz'
    s.number = 3
    cancel = message(3, 'Cancelar')
    s.repo.ingest_events([cancel], 4)
    before = s.state()
    original = s.repo._complete_reply

    def fail(*args):
        original(*args)
        raise RuntimeError('reset-failpoint')

    with monkeypatch.context() as patch:
        patch.setattr(s.repo, '_complete_reply', fail)
        with pytest.raises(RuntimeError, match='reset-failpoint'):
            asyncio.run(s.conversation.handle(cancel, 'dry_run'))
    assert s.state() == before
    assert s.repo.event_result(3)[1] is None
    asyncio.run(s.conversation.handle(cancel, 'dry_run'))
    assert Repository(s.repo.path).guided_history(7, 7) == ()
    s.new_topic('leche')
    assert s.pending_names() == ['leche']


def test_oversized_source_choices_keep_all_rows_without_offering_tokens(tmp_path):
    s = Session(tmp_path)
    from shopping_agent.contracts import ProposeChange
    from shopping_agent.guided_contracts import ChangeCandidate
    from tests.guided_helpers import message
    name = 'leche ' + 'x' * 154
    s.repo.ingest_events([message(1, '/anadir ejemplo 1')], 2)
    s.repo.complete_agent_reply(1, Reply(text='Semilla sintética'))
    with s.repo._connection(write=True) as db:
        for i in range(24):
            db.execute('INSERT INTO list_lines VALUES (?,NULL,?,2,1,1)', (f'row-{i}', name))
    s.number = 2
    s.repo.ingest_events([message(2, 'añade tres más de ' + name)], 3)
    reply = s.repo.apply_guided(2, ChangeCandidate(source_update_id=2,
        change=ProposeChange(kind='increment', query=name, quantity=3)),
        expected_question_version=None, now=s.now)
    state = s.state()
    assert state.question.kind == 'source_line'
    assert len(state.question.choices) == 24
    assert reply.keyboard is None and review_fits(reply)
    assert len(s.saved()) == 24
    assert len(state.snapshot.proposal.items[0].candidates) == 24
    s.repo.assert_authorized_owner(7)


def test_corrupted_callback_reoffer_is_not_silently_excluded(tmp_path):
    c = persisted_case(tmp_path)
    c.ingest_callback(2, c.choice_token('one_each'), message_id=999)
    c.repo.apply_guided_callback(2, now=c.now)
    assert len(c.repo.guided_history(7, 7)) == 2
    q = c.question()
    with c.repo._connection(write=True) as db:
        db.execute('DELETE FROM guided_tokens WHERE question_id=? AND choice_index=0', (str(q.id),))
    with pytest.raises(ValueError):
        c.repo.guided_history(7, 7)


def test_fresh_deterministic_command_resets_expired_legacy_recipient(tmp_path):
    s = Session(tmp_path)
    s.send('/anadir arroz')
    s.now += timedelta(minutes=16)
    s.send('/anadir 2 leche')
    assert [(r.description, r.quantity) for r in s.saved()] == [('leche', 2)]
    assert s.repo.guided_history(7, 7) == ()
    s.new_topic('leche')  # A saved duplicate remains a real conflict, not expired memory.
    request = json.loads(s.calls[-1].content)
    assert 'arroz' not in json.dumps(request['messages'][1:])

