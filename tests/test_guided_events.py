import sqlite3

import pytest

from domain import InlineButton, InlineKeyboard, Intent, Reply
from storage import Repository
from tests.guided_helpers import NOW, VALID_TOKEN, callback, message, state_fixture


@pytest.fixture
def repo(tmp_path):
    repo = Repository(tmp_path / 'synthetic.db')
    repo.migrate()
    return repo


def test_mixed_events_are_ordered_and_callbacks_are_not_messages(repo):
    events = [message(2, 'hola'), callback(3, VALID_TOKEN)]
    repo.ingest_events(events[::-1], 4)
    assert repo.pending_events() == events
    assert repo.pending_messages() == events[:1]
    assert repo.event_result(3) == (events[1], None)
    with pytest.raises(TypeError, match='callback'):
        repo.message_result(3)
    with repo._connection() as db:
        assert db.execute('SELECT text FROM inbox WHERE update_id=3').fetchone()[0] == ''


@pytest.mark.parametrize('change', [message(2, 'different'), message(2, 'hola', owner=8),
                                   callback(2, VALID_TOKEN)])
def test_update_replay_compares_identity_before_ignore(repo, change):
    repo.ingest_batch([message(2, 'hola')], 3)
    with pytest.raises(ValueError):
        repo.ingest_events([message(4, 'rollback'), change], 5)
    assert repo.telegram_offset() == 3
    assert repo.pending_events() == [message(2, 'hola')]


def test_query_replay_is_idempotent_but_conflicts_fail_closed(repo):
    repo.ingest_events([callback(2, VALID_TOKEN)], 3)
    repo.ingest_events([callback(3, VALID_TOKEN)], 4)
    assert [e.update_id for e in repo.pending_events()] == [2]
    assert repo.pending_callback_acks() == ['query']
    with pytest.raises(ValueError):
        repo.ingest_events([callback(4, VALID_TOKEN, owner=8)], 5)
    with pytest.raises(ValueError):
        repo.ingest_events([callback(4, 'q:' + 'B' * 22)], 5)
    assert repo.telegram_offset() == 4


def test_failed_insert_rolls_back_cursor_and_prior_events(repo):
    with repo._connection() as db:
        db.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON inbox WHEN NEW.update_id=3 "
                   "BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        repo.ingest_events([message(2, 'hola'), callback(3, VALID_TOKEN)], 4)
    assert repo.telegram_offset() == 0
    assert repo.pending_events() == []


@pytest.mark.parametrize('expired', [False, True])
def test_ack_survives_restart_and_does_not_complete_business_event(repo, expired):
    repo.ingest_events([callback(2, VALID_TOKEN)], 3)
    restarted = Repository(repo.path)
    assert restarted.pending_callback_acks() == ['query']
    restarted.mark_callback_ack('query', expired=expired)
    restarted.mark_callback_ack('query', expired=not expired)
    assert restarted.pending_callback_acks() == []
    assert restarted.pending_events() == [callback(2, VALID_TOKEN)]
    with restarted._connection() as db:
        assert db.execute('SELECT callback_ack_state FROM inbox').fetchone()[0] == (
            'expired' if expired else 'sent')


def complete(repo, event, reply):
    repo.ingest_events([event], event.update_id + 1)
    with repo._connection(write=True) as db:
        source = db.execute('SELECT * FROM inbox WHERE update_id=?', (event.update_id,)).fetchone()
        repo._complete_reply(db, source, reply)
    return repo.pending_replies()[0][0]


def test_keyboard_reply_and_multiple_receipts_roundtrip_without_marking_sent(repo):
    reply = Reply(text='choose', keyboard=InlineKeyboard(rows=(
        (InlineButton(label='one', token=VALID_TOKEN),),)))
    notice = complete(repo, callback(2, VALID_TOKEN), reply)
    assert repo.event_result(2)[1] == reply
    assert repo.pending_replies() == [(notice, 7, reply)]
    assert repo.pending_notices() == [(notice, 7, 'choose')]
    for mid in (100, 101):
        repo.record_delivery(notice, 7, mid, 'digest')
        repo.record_delivery(notice, 7, mid, 'digest')
        assert repo.known_delivery(notice, 7, mid, 'digest')
    assert not repo.known_delivery(notice, 7, 100, 'wrong')
    assert repo.pending_replies() == [(notice, 7, reply)]
    repo.assert_authorized_owner(7)


@pytest.mark.parametrize('chat,mid,digest', [(8, 100, 'digest'), (7, 0, 'digest'),
                                           (7, True, 'digest'), (7, 100, '')])
def test_invalid_receipt_rejected(repo, chat, mid, digest):
    notice = complete(repo, message(2, 'hola'), Reply(text='reply'))
    with pytest.raises(ValueError):
        repo.record_delivery(notice, chat, mid, digest)


def test_delivery_conflict_and_missing_notice_rejected(repo):
    notice = complete(repo, message(2, 'hola'), Reply(text='reply'))
    repo.record_delivery(notice, 7, 100, 'digest')
    with pytest.raises(ValueError):
        repo.record_delivery(notice, 7, 100, 'changed')
    with pytest.raises(ValueError):
        repo.record_delivery('missing', 7, 100, 'digest')


def test_unknown_delivery_never_grants_authority(repo):
    assert not repo.known_delivery('missing', 7, 100, 'digest')
    notice = complete(repo, message(2, 'hola'), Reply(text='reply'))
    assert not repo.known_delivery(notice, 8, 100, 'digest')


def retained_question(repo):
    from shopping_agent.guided_controller import next_question
    from shopping_agent.guided_replies import render_question

    event = message(2, 'hola')
    question = next_question(state_fixture(), event, now=NOW)
    tokens = tuple('q:' + chr(65 + i) * 22 for i in range(len(question.choices)))
    reply = Reply(text=render_question(question).text, keyboard=InlineKeyboard(rows=(tuple(
        InlineButton(label=choice.label, token=token)
        for choice, token in zip(question.choices, tokens, strict=True)),)))
    notice = complete(repo, event, reply)
    with repo._connection(write=True) as db:
        db.execute('INSERT INTO guided_questions VALUES (?,?,?,?,?,?,?)',
                   (str(question.id), question.version, 7, 7, 2, notice, question.model_dump_json()))
        db.executemany('INSERT INTO guided_tokens VALUES (?,7,7,?,?,?, ?,NULL,NULL)',
                       [(token, str(question.id), question.version, index, notice)
                        for index, token in enumerate(tokens)])
    return question, tokens, notice


def test_owner_checks_valid_question_and_offered_tokens(repo):
    retained_question(repo)
    repo.assert_authorized_owner(7)


@pytest.mark.parametrize('corruption', ['owner', 'payload_owner', 'choice', 'token', 'result'])
def test_owner_checks_reject_corrupted_guided_binding(repo, corruption):
    question, tokens, _notice = retained_question(repo)
    with repo._connection() as db:
        if corruption == 'owner':
            db.execute('UPDATE guided_questions SET user_id=8')
        elif corruption == 'payload_owner':
            payload = question.model_copy(update={'owner_id': 8}).model_dump_json()
            db.execute('UPDATE guided_questions SET question_json=?', (payload,))
        elif corruption == 'choice':
            db.execute('UPDATE guided_tokens SET choice_index=99')
        elif corruption == 'token':
            db.execute('UPDATE guided_tokens SET token=? WHERE token=?',
                       ('q:' + 'Z' * 22, tokens[0]))
        else:
            db.execute('UPDATE guided_tokens SET consumed_update_id=2,result_json=?',
                       (Reply(text='invented result').model_dump_json(),))
    with pytest.raises(PermissionError):
        repo.assert_authorized_owner(7)


def test_owner_checks_reject_callback_payload_identity_tampering(repo):
    repo.ingest_events([callback(2, VALID_TOKEN)], 3)
    with repo._connection() as db:
        db.execute('UPDATE inbox SET payload_json=?',
                   (callback(2, VALID_TOKEN, owner=8).model_dump_json(),))
    with pytest.raises(PermissionError):
        repo.assert_authorized_owner(7)


def test_callback_cannot_enter_legacy_execution(repo):
    repo.ingest_events([callback(2, VALID_TOKEN)], 3)
    with pytest.raises(ValueError, match='callback'):
        repo.apply_intent(2, Intent(action='add'), 'dry_run')
    with pytest.raises(ValueError, match='callback'):
        repo.prepare_dialogue(2, None, 'dry_run', now=NOW)
    with pytest.raises(ValueError, match='callback'):
        repo.apply_dialogue(2, None, 'dry_run', now=NOW)
    with pytest.raises(ValueError, match='callback'):
        repo.agent_snapshot(2, now=NOW)
    assert repo.list_lines() == []


def test_generative_callback_job_rejected(repo):
    repo.ingest_events([callback(2, VALID_TOKEN)], 3)
    with repo._connection() as db:
        db.execute("INSERT INTO presentation_jobs VALUES (2,7,7,'{}','synthetic')")
    with pytest.raises(ValueError, match='callback'):
        repo.prepared_presentation(2)


@pytest.mark.parametrize('table', ['guided_questions', 'guided_topics', 'guided_tokens',
                                 'telegram_deliveries'])
def test_owner_check_rejects_orphan_new_state(repo, table):
    # Corrupt retained state is not authorized merely because owner columns look right.
    with sqlite3.connect(repo.path) as db:
        if table == 'guided_questions':
            db.execute("INSERT INTO guided_questions VALUES ('q',1,7,7,2,'notice','{}')")
        elif table == 'guided_topics':
            db.execute("INSERT INTO guided_topics VALUES ('t',1,7,7,2,'{}')")
        elif table == 'guided_tokens':
            db.execute('INSERT INTO guided_tokens VALUES (?,7,7,\'q\',1,0,\'notice\',NULL,NULL)',
                       (VALID_TOKEN,))
        else:
            db.execute("INSERT INTO telegram_deliveries VALUES ('notice',7,100,'digest')")
    with pytest.raises(PermissionError):
        repo.assert_authorized_owner(7)
