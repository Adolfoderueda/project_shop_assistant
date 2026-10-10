import asyncio
import sqlite3
from hashlib import sha256
from unittest.mock import AsyncMock

import pytest
from telegram import Message, Update, User
from telegram.error import BadRequest, NetworkError

from domain import IncomingCallback, InlineButton, InlineKeyboard, Reply
from storage import Repository
from telegram_io import TelegramIO
from tests.guided_helpers import persisted_case
from tests.test_telegram_io import update


class TelegramStub:
    """Only the external boundary is fake; PTB models and repository are real."""

    def __init__(self, bot_id=99):
        self.bot_id = bot_id
        self.updates = ()
        self.sent = []
        self.acks = []
        self.polls = []
        self.send_failures = []
        self.ack_error = None
        self.repo = None

    async def get_me(self):
        return User(self.bot_id, 'Our bot', True)

    async def get_updates(self, **kwargs):
        self.polls.append(kwargs)
        return self.updates

    async def send_message(self, **kwargs):
        result = Message.de_json({
            'message_id': 100 + len(self.sent), 'date': 1,
            'chat': {'id': kwargs['chat_id'], 'type': 'private'},
            'from': {'id': self.bot_id, 'is_bot': True, 'first_name': 'Our bot'},
            'text': kwargs['text'],
            'reply_markup': kwargs['reply_markup'].to_dict() if kwargs.get('reply_markup') else None,
        }, None)
        self.sent.append((kwargs, result))
        if self.send_failures:
            error = self.send_failures.pop(0)
            if error:
                raise error
        return result

    async def answer_callback_query(self, **kwargs):
        # Durable BEFORE the network, not a business completion or synthetic text.
        assert kwargs['callback_query_id'] in self.repo.pending_callback_acks()
        self.acks.append(kwargs)
        if self.ack_error:
            raise self.ack_error
        return True


def callback_update(number, token, *, user=7, chat=7, bot_id=99, **changes):
    query = {
        'id': f'query-{number}', 'from': {'id': user, 'is_bot': False, 'first_name': 'Owner'},
        'chat_instance': 'instance', 'data': token,
        'message': {'message_id': 100, 'date': 1, 'text': '/comprar',
                    'chat': {'id': chat, 'type': 'private'},
                    'from': {'id': bot_id, 'is_bot': True, 'first_name': 'Our bot'}},
    }
    query.update(changes)
    return Update.de_json({'update_id': number, 'callback_query': query}, None)


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr('telegram_io.asyncio.sleep', AsyncMock())


def transport(c):
    bot = TelegramStub()
    bot.repo = c.repo
    return bot, TelegramIO(bot, c.repo, 7)


def receipts(repo):
    with sqlite3.connect(repo.path) as db:
        return db.execute('SELECT notice_id,chat_id,message_id,digest FROM telegram_deliveries').fetchall()


def test_mixed_batch_durable_callback_acked_before_dispatch(tmp_path):
    c = persisted_case(tmp_path)
    bot, io = transport(c)
    bot.updates = (update(2, text='lista'), callback_update(3, c.choice_token('one_each')))
    asyncio.run(io.poll_once())
    reopened = Repository(c.repo.path)
    assert reopened.telegram_offset() == 4
    assert bot.polls[0]['allowed_updates'] == ['message', 'callback_query']
    events = reopened.pending_events()
    assert [e.update_id for e in events] == [2, 3]
    assert isinstance(events[1], IncomingCallback)
    assert events[1].bot_id == 99
    assert reopened.event_result(3)[1] is None
    assert reopened.pending_callback_acks() == []
    assert bot.acks == [{'callback_query_id': 'query-3'}]
    with sqlite3.connect(c.repo.path) as db:
        assert db.execute('SELECT text FROM inbox WHERE update_id=3').fetchone() == ('',)
    assert c.repo.list_lines() == []


@pytest.mark.parametrize('change', [
    {'user': 8}, {'chat': 8}, {'chat': -7}, {'bot_id': 98},
    {'from': {'id': 7, 'is_bot': True, 'first_name': 'Bot'}},
    {'inline_message_id': 'inline'}, {'game_short_name': 'game'},
    {'data': None}, {'data': 123}, {'data': '1'}, {'data': 'q:' + 'A' * 21},
    {'message': None},
    {'message': {'message_id': 100, 'date': 0, 'chat': {'id': 7, 'type': 'private'}}},
    {'message': {'message_id': 100, 'date': 1, 'chat': {'id': 7, 'type': 'group'},
                 'from': {'id': 99, 'is_bot': True, 'first_name': 'Bot'}}},
    {'message': {'message_id': 100, 'date': 1, 'chat': {'id': 7, 'type': 'private'},
                 'from': {'id': 99, 'is_bot': False, 'first_name': 'Not bot'}}},
])
def test_bad_callback_never_persists_content(tmp_path, change):
    c = persisted_case(tmp_path)
    bot, io = transport(c)
    bot.updates = (callback_update(2, c.choice_token('one_each'), **change),)
    asyncio.run(io.poll_once())
    assert c.repo.pending_events() == []
    assert c.repo.telegram_offset() == 3
    assert c.repo.pending_callback_acks() == []
    with sqlite3.connect(c.repo.path) as db:
        assert db.execute('SELECT count(*) FROM inbox').fetchone()[0] == 1
    assert bot.acks == []


def test_unknown_format_valid_token_is_not_choice_authority(tmp_path):
    c = persisted_case(tmp_path)
    bot, io = transport(c)
    bot.updates = (callback_update(2, 'q:' + 'A' * 22),)
    asyncio.run(io.poll_once())
    c.repo.apply_guided_callback(2, now=c.now)
    assert [p.quantity for p in c.repo.guided_state(2, now=c.now).snapshot.proposal.items] == [None] * 3
    assert c.repo.list_lines() == []


def test_unregistered_message_cannot_authorize_a_known_token(tmp_path):
    c = persisted_case(tmp_path)
    c.ingest_callback(2, c.choice_token('one_each'), message_id=999)
    c.repo.apply_guided_callback(2, now=c.now)
    assert [p.quantity for p in c.repo.guided_state(2, now=c.now).snapshot.proposal.items] == [None] * 3
    assert c.repo.list_lines() == []


def test_full_rendered_delivery_authenticates_quantity_not_save(tmp_path):
    c = persisted_case(tmp_path)
    bot, io = transport(c)
    token = c.choice_token('one_each')
    notice, chat, reply = c.repo.pending_replies()[0]
    asyncio.run(io.send_pending())
    sent, message = bot.sent[0]
    assert sent['text'] == reply.text
    assert sent['reply_markup'].inline_keyboard[0][0].callback_data == reply.keyboard.rows[0][0].token
    assert receipts(c.repo) == [(notice, chat, message.message_id, sha256(reply.text.encode()).hexdigest())]
    assert c.repo.pending_replies() == []
    bot.updates = (callback_update(2, token),)
    asyncio.run(io.poll_once())
    c.repo.apply_guided_callback(2, now=c.now)
    assert [p.quantity for p in c.repo.guided_state(2, now=c.now).snapshot.proposal.items] == [1] * 3
    assert c.repo.list_lines() == []


@pytest.mark.parametrize('error,terminal', [
    (NetworkError('secret'), False),
    (BadRequest('Query is too old and response timeout expired or query ID is invalid'), True),
    (BadRequest('unrelated rejection'), False),
])
def test_restart_ack_independent_of_processing_and_notices(tmp_path, error, terminal):
    c = persisted_case(tmp_path)
    c.ingest_callback(2, c.choice_token('one_each'))
    bot, io = transport(c)
    bot.ack_error = error
    asyncio.run(io.ack_callbacks())
    assert c.repo.pending_callback_acks() == ([] if terminal else ['query-2'])
    assert c.repo.event_result(2)[1] is None
    bot.repo = Repository(c.repo.path)
    bot.ack_error = None
    restarted = TelegramIO(bot, bot.repo, 7)
    asyncio.run(restarted.poll_once())  # Empty polling still recovers durable acks.
    assert bot.repo.pending_callback_acks() == []
    asyncio.run(restarted.send_pending())
    assert bot.repo.pending_notices() == []
    assert bot.repo.event_result(2)[1] is None


def test_ack_owner_checks_before_network(tmp_path):
    c = persisted_case(tmp_path)
    c.ingest_callback(2, c.choice_token('one_each'))
    bot, _ = transport(c)
    with pytest.raises(PermissionError):
        asyncio.run(TelegramIO(bot, c.repo, 8).ack_callbacks())
    assert bot.acks == []
    assert c.repo.pending_callback_acks() == ['query-2']


def test_ingest_failure_never_acks_or_advances(tmp_path):
    c = persisted_case(tmp_path)
    bot, io = transport(c)
    bot.updates = (callback_update(2, c.choice_token('one_each')),)
    with sqlite3.connect(c.repo.path) as db:
        db.executescript("CREATE TRIGGER fail BEFORE UPDATE ON meta BEGIN SELECT RAISE(ABORT,'injected'); END;")
    with pytest.raises(sqlite3.IntegrityError):
        asyncio.run(io.poll_once())
    assert c.repo.telegram_offset() == 2
    assert c.repo.pending_callback_acks() == []
    assert bot.acks == []


def test_uncertain_send_unknown_copy_then_known_copy_single_transition(tmp_path):
    c = persisted_case(tmp_path)
    bot, io = transport(c)
    original_token = c.choice_token('one_each')
    bot.send_failures = [NetworkError('response lost')]
    asyncio.run(io.send_pending())
    assert len(bot.sent) == 2
    assert bot.sent[0][0]['reply_markup'] == bot.sent[1][0]['reply_markup']
    assert [r[2] for r in receipts(c.repo)] == [101]
    c.ingest_callback(2, original_token, message_id=100)
    c.repo.apply_guided_callback(2, now=c.now)
    assert [p.quantity for p in c.repo.guided_state(2, now=c.now).snapshot.proposal.items] == [None] * 3
    assert c.repo.pending_replies()[0][2].keyboard is not None
    # Unknown-copy reoffer revokes the old question, without renewing expiry.
    asyncio.run(TelegramIO(bot, Repository(c.repo.path), 7).send_pending())
    token = c.choice_token('one_each')
    c.ingest_callback(3, token, message_id=102)
    c.repo.apply_guided_callback(3, now=c.now)
    c.ingest_callback(4, token, message_id=102)
    c.repo.apply_guided_callback(4, now=c.now)
    assert [p.quantity for p in c.repo.guided_state(4, now=c.now).snapshot.proposal.items] == [1] * 3
    assert c.repo.list_lines() == []


def test_crash_after_receipt_before_sent_marker_retains_both_copies(tmp_path):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    bot, io = transport(c)
    token = c.choice_token('confirm')
    with sqlite3.connect(c.repo.path) as db:
        db.executescript("CREATE TRIGGER fail BEFORE UPDATE ON outbox BEGIN SELECT RAISE(ABORT,'injected'); END;")
    with pytest.raises(sqlite3.IntegrityError):
        asyncio.run(io.send_pending())
    assert len(receipts(c.repo)) == 1
    assert c.repo.pending_replies()
    with sqlite3.connect(c.repo.path) as db:
        db.execute('DROP TRIGGER fail')
    asyncio.run(TelegramIO(bot, Repository(c.repo.path), 7).send_pending())
    assert [r[2] for r in receipts(c.repo)] == [100, 101]
    assert c.repo.pending_replies() == []
    c.ingest_callback(2, token, message_id=100)
    c.repo.apply_guided_callback(2, now=c.now)
    lines = c.repo.list_lines()
    assert len(lines) == 3
    c.ingest_callback(3, token, message_id=101)
    c.repo.apply_guided_callback(3, now=c.now)
    assert c.repo.list_lines() == lines


def test_astral_oversized_keyboard_never_fragmented_or_accredited(tmp_path):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    bot, io = transport(c)
    notice, _, _ = c.repo.pending_replies()[0]
    oversized = Reply(text='😀' * 2001, keyboard=InlineKeyboard(rows=((
        InlineButton(label='Confirmar', token=c.choice_token('confirm')),),)))
    # Defense in depth against an invalid oversized producer; no new authority.
    with sqlite3.connect(c.repo.path) as db:
        db.execute('UPDATE outbox SET reply_json=? WHERE id=?', (oversized.model_dump_json(), notice))
    asyncio.run(io.send_pending())
    assert bot.sent == []
    assert receipts(c.repo) == []
    assert c.repo.pending_replies()[0][2] == oversized


def test_ack_recovers_completed_callback_without_reopening_business(tmp_path):
    c = persisted_case(tmp_path)
    c.record_known_delivery()
    c.ingest_callback(2, c.choice_token('one_each'))
    reply = c.repo.apply_guided_callback(2, now=c.now)
    reopened = Repository(c.repo.path)
    bot = TelegramStub()
    bot.repo = reopened
    asyncio.run(TelegramIO(bot, reopened, 7).poll_once())
    assert reopened.pending_callback_acks() == []
    assert reopened.pending_events() == []
    assert reopened.event_result(2)[1] == reply
    assert reopened.list_lines() == []


def test_expired_ack_never_repeats_confirmed_operation(tmp_path):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    c.record_known_delivery()
    c.ingest_callback(2, c.choice_token('confirm'))
    c.repo.apply_guided_callback(2, now=c.now)
    lines = c.repo.list_lines()
    bot, io = transport(c)
    bot.ack_error = BadRequest('Query_id_invalid')
    asyncio.run(io.ack_callbacks())
    assert c.repo.pending_callback_acks() == []
    assert c.repo.list_lines() == lines
    assert len(lines) == 3
    assert c.repo.pending_events() == []
    asyncio.run(io.send_pending())
    assert c.repo.pending_notices() == []


def test_bot_identity_network_failure_does_not_ingest_callback(tmp_path):
    c = persisted_case(tmp_path)
    bot, io = transport(c)
    bot.updates = (callback_update(2, c.choice_token('one_each')),)
    bot.get_me = AsyncMock(side_effect=NetworkError('private'))
    with pytest.raises(NetworkError):
        asyncio.run(io.poll_once())
    assert c.repo.telegram_offset() == 2
    assert c.repo.pending_events() == []
    assert c.repo.pending_callback_acks() == []


def test_wrong_send_response_chat_cannot_accredit_delivery(tmp_path):
    c = persisted_case(tmp_path, quantities=(1, 1, 1))
    bot, io = transport(c)
    bot.send_message = AsyncMock(return_value=update(100, chat=8).message)
    with pytest.raises(ValueError, match='delivery response'):
        asyncio.run(io.send_pending())
    assert receipts(c.repo) == []
    assert c.repo.pending_replies()


def test_uncertain_sends_restart_preserves_offer_until_known_delivery(tmp_path, caplog):
    c = persisted_case(tmp_path)
    bot, io = transport(c)
    token = c.choice_token('one_each')
    pending = c.repo.pending_replies()
    bot.send_failures = [NetworkError('SECRET_PRIVATE') for _ in range(3)]
    asyncio.run(io.send_pending())
    assert receipts(c.repo) == []
    assert c.repo.pending_replies() == pending
    reopened = Repository(c.repo.path)
    asyncio.run(TelegramIO(bot, reopened, 7).send_pending())
    assert len(bot.sent) == 4
    assert all(s[0]['reply_markup'] == bot.sent[0][0]['reply_markup'] for s in bot.sent)
    assert [r[2] for r in receipts(reopened)] == [103]
    c.ingest_callback(2, token, message_id=103)
    c.repo.apply_guided_callback(2, now=c.now)
    state = c.repo.guided_state(2, now=c.now)
    c.ingest_callback(3, token, message_id=103)
    c.repo.apply_guided_callback(3, now=c.now)
    replay = c.repo.guided_state(3, now=c.now)
    assert replay.snapshot.proposal == state.snapshot.proposal
    assert replay.question == state.question
    assert replay.review == state.review
    assert c.repo.list_lines() == []
    assert token not in caplog.text
    assert 'SECRET_PRIVATE' not in caplog.text
    assert pending[0][2].text not in caplog.text


def test_ack_cancellation_leaves_durable_pending(tmp_path):
    c = persisted_case(tmp_path)
    c.ingest_callback(2, c.choice_token('one_each'))
    bot, io = transport(c)
    bot.ack_error = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(io.ack_callbacks())
    assert Repository(c.repo.path).pending_callback_acks() == ['query-2']
    assert c.repo.event_result(2)[1] is None
