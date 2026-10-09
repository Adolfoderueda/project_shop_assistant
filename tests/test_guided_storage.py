from datetime import timedelta

import pytest

from tests.guided_helpers import candidate, persisted_case


def test_model_clarify_cannot_confirm_delivered_review(tmp_path):
    from shopping_agent.guided_contracts import ControlCandidate

    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    c.record_known_delivery()
    c.ingest_message(2, 'sí')
    c.repo.apply_guided(2, ControlCandidate(kind='clarify'),
                        expected_question_version=c.question().version, now=c.now)
    assert c.repo.list_lines() == []
    assert c.repo.guided_state(2, now=c.now).snapshot.proposal.revision == 1


@pytest.mark.parametrize('kind', ['quantity', 'list', 'cancel'])
def test_model_candidates_never_recover_confirmation_authority(tmp_path, kind):
    from shopping_agent.guided_contracts import ControlCandidate, ReadCandidate

    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    c.record_known_delivery()
    c.ingest_message(2, 'sí')
    answer = (candidate(2, (1, 2)) if kind == 'quantity' else
              ReadCandidate(kind='list') if kind == 'list' else ControlCandidate(kind='cancel'))
    c.repo.apply_guided(2, answer, expected_question_version=c.question().version, now=c.now)
    assert c.repo.list_lines() == []
    assert c.repo.guided_state(2, now=c.now).snapshot.proposal is not None


@pytest.mark.parametrize('kind', ['clarify', 'cancel'])
@pytest.mark.parametrize('text', ['sí', 'no'])
def test_model_control_cannot_resolve_pending_topic(tmp_path, kind, text):
    from shopping_agent.contracts import ItemInput, ProposeAdds
    from shopping_agent.guided_contracts import ControlCandidate, TopicCandidate
    from shopping_agent.guided_controller import resolve_text_choice

    c = persisted_case(tmp_path)
    c.ingest_message(2, 'leche')
    c.repo.apply_guided(2, TopicCandidate(source_update_id=2,
        adds=ProposeAdds(items=(ItemInput(description='leche'),))),
        expected_question_version=c.question().version, now=c.now)
    before = c.repo.guided_state(2, now=c.now)
    c.ingest_message(3, text)
    c.repo.apply_guided(3, ControlCandidate(kind=kind),
        expected_question_version=before.question.version, now=c.now)
    after = c.repo.guided_state(3, now=c.now)
    assert after.topic == before.topic
    assert after.snapshot.proposal == before.snapshot.proposal
    assert c.repo.list_lines() == []
    # The same original application choice remains usable on a later event.
    c.ingest_message(4, text)
    event, _ = c.repo.event_result(4)
    choice = resolve_text_choice(event, after.question)
    assert choice is not None
    c.repo.apply_guided(4, choice, expected_question_version=after.question.version, now=c.now)
    result = c.repo.guided_state(4, now=c.now)
    assert result.topic is None
    assert len(result.snapshot.proposal.items) == (4 if text == 'sí' else 3)
    assert c.repo.list_lines() == []


def test_callback_quantity_never_saves_and_replay_consumes_once(tmp_path):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    token = c.choice_token('one_each')
    c.ingest_callback(2, token)
    first = c.repo.apply_guided_callback(2, now=c.now)
    assert c.repo.list_lines() == []
    assert c.repo.apply_guided_callback(2, now=c.now) == first
    assert c.repo.guided_state(2, now=c.now).snapshot.proposal.revision == 2
    c.ingest_callback(3, token)
    assert c.repo.apply_guided_callback(3, now=c.now) == first
    assert c.repo.guided_state(3, now=c.now).snapshot.proposal.revision == 2


def test_final_confirmation_requires_delivery_and_saves_once(tmp_path):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    c.ingest_message(2, 'sí')
    c.repo.apply_guided(2, None, expected_question_version=c.question().version, now=c.now)
    assert c.repo.list_lines() == []
    c.record_known_delivery()
    c.ingest_callback(3, c.choice_token('confirm'))
    reply = c.repo.apply_guided_callback(3, now=c.now)
    lines = c.repo.list_lines()
    assert len(lines) == 3
    assert c.repo.apply_guided_callback(3, now=c.now) == reply
    assert c.repo.list_lines() == lines


def test_other_choice_and_unknown_delivery_do_not_change_state(tmp_path):
    c = persisted_case(tmp_path)
    other = c.choice_token('different_quantities')
    c.ingest_callback(2, c.choice_token('one_each'), message_id=101)
    c.repo.apply_guided_callback(2, now=c.now)
    assert c.repo.guided_state(2, now=c.now).snapshot.proposal.revision == 1
    c.record_known_delivery()
    c.ingest_callback(3, c.choice_token('one_each'))
    c.repo.apply_guided_callback(3, now=c.now)
    c.ingest_callback(4, other)
    assert 'anterior' in c.repo.apply_guided_callback(4, now=c.now).text
    assert c.repo.guided_state(4, now=c.now).snapshot.proposal.revision == 2


def test_old_callback_after_edit_and_expiry_do_not_save(tmp_path):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    c.record_known_delivery()
    token = c.choice_token('confirm')
    c.ingest_message(2, 'cambia la cantidad')
    c.repo.apply_guided(2, candidate(2, (1, 2)), expected_question_version=c.question().version, now=c.now)
    c.ingest_callback(3, token)
    c.repo.apply_guided_callback(3, now=c.now)
    assert c.repo.list_lines() == []
    c.ingest_message(4, 'sí')
    c.repo.apply_guided(4, None, expected_question_version=c.question().version,
                        now=c.now + timedelta(minutes=16))
    assert c.repo.list_lines() == []


@pytest.mark.parametrize('point', ['_complete_reply', '_write_agent_proposal'])
@pytest.mark.parametrize('phase', ['before', 'after'])
def test_commit_rolls_back_state_outbox_and_consumption(tmp_path, monkeypatch, point, phase):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    token = c.choice_token('one_each')
    c.ingest_callback(2, token)
    original = getattr(c.repo, point)

    def fail(*args, **kwargs):
        if phase == 'after':
            original(*args, **kwargs)
        raise RuntimeError('failpoint')

    monkeypatch.setattr(c.repo, point, fail)
    with pytest.raises(RuntimeError, match='failpoint'):
        c.repo.apply_guided_callback(2, now=c.now)
    monkeypatch.setattr(c.repo, point, original)
    assert c.repo.event_result(2)[1] is None
    assert c.repo.guided_state(2, now=c.now).snapshot.proposal.revision == 1
    assert len(c.repo.pending_replies()) == 1
    c.repo.apply_guided_callback(2, now=c.now)
    assert c.repo.guided_state(2, now=c.now).snapshot.proposal.revision == 2


def test_quantity_then_separate_final_event_saves_exactly_three(tmp_path):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    c.ingest_callback(2, c.choice_token('one_each'))
    c.repo.apply_guided_callback(2, now=c.now)
    assert not c.repo.list_lines()
    c.record_known_delivery(message_id=200)
    token = c.choice_token('confirm')
    c.ingest_callback(3, token, message_id=200)
    reply = c.repo.apply_guided_callback(3, now=c.now)
    assert len(c.repo.list_lines()) == 3
    ids = [(line.id, line.revision) for line in c.repo.list_lines()]
    c.ingest_callback(4, token, message_id=200)
    assert c.repo.apply_guided_callback(4, now=c.now) == reply
    assert [(line.id, line.revision) for line in c.repo.list_lines()] == ids
    c.repo.assert_authorized_owner(7)


def test_undelivered_confirmation_resends_full_review(tmp_path):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    previous = c.question()
    c.ingest_message(2, 'sí')
    reply = c.repo.apply_guided(2, None, expected_question_version=previous.version, now=c.now)
    current = c.question()
    assert reply.text == previous.text
    assert reply.keyboard is not None
    assert current.version == previous.version + 1
    assert current.source_update_id == 2
    assert not c.repo.list_lines()
    c.record_known_delivery()
    c.ingest_message(3, 'sí')
    c.repo.apply_guided(3, None, expected_question_version=current.version, now=c.now)
    assert len(c.repo.list_lines()) == 3


def test_yes_scope_and_topic_keep_do_not_save_or_reuse_witness(tmp_path):
    from shopping_agent.contracts import ItemInput, ProposeAdds
    from shopping_agent.guided_contracts import TopicCandidate

    c = persisted_case(tmp_path)
    c.ingest_message(2, 'sí')
    c.repo.apply_guided(2, None, expected_question_version=c.question().version, now=c.now)
    assert not c.repo.list_lines()
    c.record_known_delivery()
    c.ingest_callback(3, c.choice_token('one_each'))
    c.repo.apply_guided_callback(3, now=c.now)
    c.record_known_delivery(message_id=200)
    c.ingest_message(4, 'leche')
    c.repo.apply_guided(4, TopicCandidate(source_update_id=4,
        adds=ProposeAdds(items=(ItemInput(description='leche'),))),
        expected_question_version=c.question().version, now=c.now)
    assert c.repo.guided_state(4, now=c.now).review is None
    c.ingest_message(5, 'no')
    c.repo.apply_guided(5, None, expected_question_version=c.question().version, now=c.now)
    assert c.repo.guided_state(5, now=c.now).review.delivered_message_id is None
    c.ingest_message(6, 'sí')
    c.repo.apply_guided(6, None, expected_question_version=c.question().version, now=c.now)
    assert not c.repo.list_lines()


def test_reads_preserve_question_and_absolute_expiry(tmp_path):
    from shopping_agent.guided_contracts import ReadCandidate

    c = persisted_case(tmp_path)
    before = c.repo.guided_state(1, now=c.now)
    c.ingest_message(2, 'qué hay en la lista')
    c.repo.apply_guided(2, ReadCandidate(kind='list'), expected_question_version=c.question().version,
                        now=c.now + timedelta(minutes=1))
    after = c.repo.guided_state(2, now=c.now)
    assert after.question == before.question
    assert after.snapshot.proposal == before.snapshot.proposal


def test_resolved_choice_is_reauthenticated_against_original_text(tmp_path):
    from shopping_agent.guided_contracts import ResolvedChoice

    c = persisted_case(tmp_path)
    q = c.question()
    c.ingest_message(2, 'Uno de cada')
    answer = ResolvedChoice(question_id=q.id, question_version=q.version, choice_index=0, source_update_id=2)
    c.repo.apply_guided(2, answer, expected_question_version=q.version, now=c.now)
    assert c.repo.guided_state(2, now=c.now).snapshot.proposal.revision == 2
    c.ingest_message(3, 'no autoriza ninguna opción')
    with pytest.raises(ValueError, match='Choice'):
        c.repo.apply_guided(3, answer.model_copy(update={'source_update_id': 3}),
                           expected_question_version=c.question().version, now=c.now)


def test_v2_cannot_be_confirmed_or_replaced_by_legacy_reducer(tmp_path):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    before = c.repo.guided_state(1, now=c.now).snapshot.proposal
    c.ingest_message(2, 'sí')
    c.repo.apply_agent_control(2, now=c.now)
    assert not c.repo.list_lines()
    assert c.repo.guided_state(2, now=c.now).snapshot.proposal == before
    c.ingest_message(3, 'otra petición')
    c.repo.apply_agent_operation(3, 'proponer_altas',
        {'items': [{'description': 'arroz', 'quantity': 2}]}, None, now=c.now)
    assert c.repo.guided_state(3, now=c.now).snapshot.proposal == before


def test_final_batch_write_failure_rolls_back_lines_and_choice(tmp_path):
    import sqlite3

    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    c.record_known_delivery()
    token = c.choice_token('confirm')
    c.ingest_callback(2, token)
    with c.repo._connection(write=True) as db:
        db.execute("CREATE TRIGGER fail_batch BEFORE INSERT ON list_lines WHEN NEW.description='carne' "
                   "BEGIN SELECT RAISE(ABORT,'batch-failpoint'); END")
    with pytest.raises(sqlite3.IntegrityError, match='batch-failpoint'):
        c.repo.apply_guided_callback(2, now=c.now)
    assert not c.repo.list_lines()
    assert c.repo.event_result(2)[1] is None
    assert c.question().status == 'active'
    with c.repo._connection(write=True) as db:
        db.execute('DROP TRIGGER fail_batch')
    c.repo.apply_guided_callback(2, now=c.now)
    assert len(c.repo.list_lines()) == 3


@pytest.mark.parametrize('damage', ['revision', 'reserved'])
def test_confirmation_revalidates_actual_increment_source(tmp_path, damage):
    from datetime import UTC, datetime

    from domain import Intent, IntentLine
    from shopping_agent.contracts import ProposeChange
    from shopping_agent.guided_contracts import ChangeCandidate
    from storage import Repository
    from tests.guided_helpers import PersistedCase

    repo = Repository(tmp_path / 'increment.db')
    repo.migrate()
    c = PersistedCase(repo=repo, now=datetime.now(UTC), source_update_id=2)
    c.ingest_message(1, '/anadir 2 leche')
    repo.apply_intent(1, Intent(action='add', lines=[IntentLine(description='leche', quantity=2)]), 'dry_run')
    line = repo.list_lines()[0]
    c.ingest_message(2, 'añade tres más de leche')
    repo.apply_guided(2, ChangeCandidate(source_update_id=2,
        change=ProposeChange(kind='increment', query='leche', quantity=3)),
        expected_question_version=None, now=c.now)
    if c.question().kind == 'source_line':
        c.ingest_message(3, '1')
        repo.apply_guided(3, None, expected_question_version=c.question().version, now=c.now)
    assert c.question().kind == 'review'
    assert '2 + 3 = 5' in c.question().text
    c.record_known_delivery()
    token = c.choice_token('confirm')
    with repo._connection(write=True) as db:
        if damage == 'revision':
            db.execute('UPDATE list_lines SET quantity=4,revision=revision+1 WHERE id=?', (line.id,))
        else:
            db.execute("INSERT INTO orders(id,source_update_id,mode,created_at) VALUES ('reserved',1,'dry_run',?)",
                       (c.now.isoformat(),))
            db.execute("INSERT INTO reservations VALUES (?,'reserved')", (line.id,))
    c.ingest_callback(4, token)
    repo.apply_guided_callback(4, now=c.now)
    assert repo.list_lines()[0].quantity == (4 if damage == 'revision' else 2)
    repo.assert_authorized_owner(7)


def test_unknown_review_copy_resends_current_notice_without_consuming_choice(tmp_path):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    previous = c.question()
    token = c.choice_token('confirm')
    c.ingest_callback(2, token, message_id=777)
    reply = c.repo.apply_guided_callback(2, now=c.now)
    assert reply.text == previous.text
    assert reply.keyboard is not None
    assert c.question().source_update_id == 2
    assert c.question().version == previous.version + 1
    with c.repo._connection() as db:
        assert db.execute('SELECT consumed_update_id FROM guided_tokens WHERE token=?', (token,)).fetchone()[0] is None
    c.record_known_delivery(message_id=200)
    c.ingest_callback(3, c.choice_token('confirm'), message_id=200)
    c.repo.apply_guided_callback(3, now=c.now)
    assert len(c.repo.list_lines()) == 3
    c.repo.assert_authorized_owner(7)


def test_callback_commit_never_uses_executable_legacy_message(tmp_path, monkeypatch):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    token = c.choice_token('one_each')
    c.ingest_callback(2, token)

    def no_legacy_message(*args):
        pytest.fail('Guided callbacks must preserve the original event, not synthesize messages')

    monkeypatch.setattr(c.repo, '_agent_message', no_legacy_message)
    c.repo.apply_guided_callback(2, now=c.now)
    event, _reply = c.repo.event_result(2)
    assert event.data == token
    with c.repo._connection() as db:
        row = db.execute('SELECT text,payload_json FROM inbox WHERE update_id=2').fetchone()
    assert row['text'] == ''
    assert token in row['payload_json']
    assert c.repo.event_result(1)[0].text == 'huevos carne atun'


def test_unchanged_clarification_keyboard_accepts_its_actual_recorded_delivery(tmp_path):
    from hashlib import sha256

    c = persisted_case(tmp_path)
    previous = c.question()
    c.ingest_message(2, 'no entiendo')
    reply = c.repo.apply_guided(2, None, expected_question_version=previous.version,
                               now=c.now + timedelta(minutes=1))
    assert reply.text == c.repo.event_result(1)[1].text
    with c.repo._connection() as db:
        notice = db.execute('SELECT id FROM outbox WHERE update_id=2').fetchone()[0]
    c.repo.record_delivery(notice, 7, 200, sha256(reply.text.encode('utf-8')).hexdigest())
    token = reply.keyboard.rows[0][0].token
    c.ingest_callback(3, token, message_id=200)
    first = c.repo.apply_guided_callback(3, now=c.now + timedelta(minutes=1))
    state = c.repo.guided_state(3, now=c.now)
    assert state.snapshot.proposal.revision == 2
    assert state.snapshot.proposal.expires_at == previous.expires_at
    assert not c.repo.list_lines()
    assert c.repo.apply_guided_callback(3, now=c.now) == first
    c.ingest_callback(4, token, message_id=200)
    assert c.repo.apply_guided_callback(4, now=c.now) == first
    assert c.repo.guided_state(4, now=c.now).snapshot.proposal.revision == 2
    c.repo.assert_authorized_owner(7)


def test_clarification_reoffer_does_not_authorize_old_token_or_unknown_copy(tmp_path):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    old_token = c.choice_token('one_each')
    previous = c.question()
    c.ingest_message(2, 'no entiendo')
    reply = c.repo.apply_guided(2, None, expected_question_version=previous.version, now=c.now)
    current = c.question()
    assert current.version == previous.version + 1
    assert current.expires_at == previous.expires_at
    c.ingest_callback(3, old_token)
    assert 'anterior' in c.repo.apply_guided_callback(3, now=c.now).text
    assert c.repo.guided_state(3, now=c.now).snapshot.proposal.revision == 1
    token = reply.keyboard.rows[0][0].token
    c.ingest_callback(4, token, message_id=777)
    reoffered = c.repo.apply_guided_callback(4, now=c.now)
    assert reoffered.text == reply.text
    assert c.repo.guided_state(4, now=c.now).snapshot.proposal.revision == 1
    assert c.question().expires_at == previous.expires_at
    c.record_known_delivery(message_id=200)
    c.ingest_callback(5, c.choice_token('one_each'), message_id=200)
    c.repo.apply_guided_callback(5, now=c.now + timedelta(minutes=16))
    assert c.repo.guided_state(5, now=c.now).snapshot.proposal.revision == 1
    assert not c.repo.list_lines()


def test_read_turn_never_reoffers_unbound_buttons_or_renews_question(tmp_path):
    from shopping_agent.guided_contracts import ReadCandidate

    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    c.record_known_delivery()
    before = c.repo.guided_state(1, now=c.now)
    c.ingest_message(2, 'qué hay en la lista')
    reply = c.repo.apply_guided(2, ReadCandidate(kind='list'), expected_question_version=c.question().version,
                               now=c.now + timedelta(minutes=1))
    assert reply.keyboard is None
    after = c.repo.guided_state(2, now=c.now)
    assert after.question == before.question
    assert after.review == before.review
    assert after.snapshot.proposal == before.snapshot.proposal
