import asyncio
import json
import sqlite3
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from telegram import Bot, Update
from telegram.error import BadRequest, RetryAfter, TimedOut
from telegram.request import BaseRequest
from telegram.warnings import PTBDeprecationWarning

from domain import IncomingMessage, Intent, IntentLine
from storage import Repository
from telegram_io import TelegramIO


def update(number, *, user=7, chat=7, kind="private", text="compra", field="message", **metadata):
    payload = {"message_id": number, "date": 1, "chat": {"id": chat, "type": kind}}
    if user is not None:
        payload["from"] = {"id": user, "is_bot": False, "first_name": "Test"}
    if text is not None:
        payload["text"] = text
    payload.update(metadata)
    return Update.de_json({"update_id": number, field: payload}, None)


@pytest.fixture
def repo(tmp_path):
    result = Repository(tmp_path / "telegram.db")
    result.migrate()
    return result


@pytest.fixture
def bot():
    # Only the network boundary is replaced; Telegram models and SQLite are real.
    result = AsyncMock(spec=Bot)
    result.send_message.return_value = update(900).message
    return result


@pytest.fixture(autouse=True)
def sleep(monkeypatch):
    monkeypatch.setenv("PTB_TIMEDELTA", "true")
    waiting = AsyncMock()
    monkeypatch.setattr("telegram_io.asyncio.sleep", waiting)
    return waiting


def notice(repo, number=1, chat=7, text="<b>Dodot</b> *literal*"):
    repo.ingest_batch([IncomingMessage(update_id=number, user_id=7, chat_id=chat, text="lista")],
                      number + 1)
    repo.apply_intent(number, Intent(action="clarify", question=text), "dry_run")
    return repo.pending_notices()[-1]


def test_unauthorized_and_group_messages_ignored(repo, bot):
    bot.get_updates.return_value = (
        update(1, user=99, text="PRIVATE_UNAUTHORIZED"),
        update(2, chat=-10, kind="group", text="PRIVATE_GROUP"),
        update(3, chat=-20, kind="supergroup"),
        update(4, user=None),
        update(5, field="edited_message"),
        update(6, text=None),
        update(7, chat=99),
        update(8, text="autorizado"),
    )
    asyncio.run(TelegramIO(bot, repo, 7).poll_once())
    assert repo.pending_messages() == [
        IncomingMessage(update_id=8, user_id=7, chat_id=7, text="autorizado")
    ]
    assert repo.telegram_offset() == 9
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT text FROM inbox").fetchall() == [("autorizado",)]
    bot.send_message.assert_not_called()


def test_crash_before_dispatch_preserves_input(repo, bot):
    bot.get_updates.return_value = (update(10), update(11, text="lista"))
    asyncio.run(TelegramIO(bot, repo, 7).poll_once())
    reopened = Repository(repo.path)
    assert [m.update_id for m in reopened.pending_messages()] == [10, 11]
    assert reopened.message_result(10)[1] is None
    assert reopened.pending_notices() == []
    bot.get_updates.return_value = ()
    asyncio.run(TelegramIO(bot, reopened, 7).poll_once())
    assert bot.get_updates.call_args.kwargs["offset"] == 12
    assert bot.get_updates.call_args.kwargs["allowed_updates"] == ["message", "callback_query"]
    assert bot.get_updates.call_args.kwargs["timeout"] > 0
    assert reopened.telegram_offset() == 12
    assert len(reopened.pending_messages()) == 2


@pytest.mark.parametrize("failure", ["insert", "offset"])
def test_offset_never_acknowledges_uncommitted_batch(repo, bot, failure):
    with sqlite3.connect(repo.path) as db:
        statement = ("BEFORE INSERT ON inbox WHEN NEW.update_id=2" if failure == "insert"
                     else "BEFORE UPDATE ON meta")
        db.executescript(f"""CREATE TRIGGER inject_failure {statement}
            BEGIN SELECT RAISE(ABORT, 'injected'); END;""")
    bot.get_updates.return_value = (update(1), update(2))
    io = TelegramIO(bot, repo, 7)
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        asyncio.run(io.poll_once())
    assert repo.pending_messages() == []
    assert repo.telegram_offset() == 0
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER inject_failure")
    asyncio.run(io.poll_once())
    assert [c.kwargs["offset"] for c in bot.get_updates.call_args_list] == [0, 0]
    assert [m.update_id for m in repo.pending_messages()] == [1, 2]
    bot.get_updates.return_value = ()
    asyncio.run(io.poll_once())
    assert bot.get_updates.call_args.kwargs["offset"] == 3


def test_ignored_only_batch_advances_and_duplicate_batch_is_idempotent(repo, bot):
    io = TelegramIO(bot, repo, 7)
    bot.get_updates.return_value = (update(1, user=99),)
    asyncio.run(io.poll_once())
    assert repo.telegram_offset() == 2
    assert repo.pending_messages() == []
    bot.get_updates.return_value = (update(2),)
    asyncio.run(io.poll_once())
    asyncio.run(io.poll_once())
    assert len(repo.pending_messages()) == 1
    assert repo.telegram_offset() == 3


def test_failed_notification_is_retried(repo, bot, caplog):
    pending = notice(repo)
    bot.send_message.side_effect = TimedOut("SECRET_TOKEN_PRIVATE_ADDRESS")
    asyncio.run(TelegramIO(bot, repo, 7).send_pending())
    assert 1 < bot.send_message.call_count <= 3
    assert Repository(repo.path).pending_notices() == [pending]
    assert pending[0] in caplog.text
    assert "SECRET_TOKEN_PRIVATE_ADDRESS" not in caplog.text
    assert pending[2] not in caplog.text
    bot.send_message.side_effect = None
    asyncio.run(TelegramIO(bot, Repository(repo.path), 7).send_pending())
    assert repo.pending_notices() == []
    sent = bot.send_message.call_args.kwargs
    assert sent["chat_id"] == 7
    assert sent["text"] == pending[2]
    assert sent["parse_mode"] is None
    assert sent["entities"] is None
    assert sent["link_preview_options"].is_disabled is True
    repo.mark_notice_sent(pending[0])  # Idempotent completion.
    assert repo.pending_notices() == []


@pytest.mark.parametrize("as_timedelta", [False, True])
def test_retry_after_waits_before_resending(repo, bot, sleep, monkeypatch, as_timedelta):
    monkeypatch.setenv("PTB_TIMEDELTA", "true" if as_timedelta else "false")
    notice(repo)
    if as_timedelta:
        bot.send_message.side_effect = [RetryAfter(timedelta(seconds=4)), update(900).message]
        asyncio.run(TelegramIO(bot, repo, 7).send_pending())
    else:
        with pytest.warns(PTBDeprecationWarning):
            bot.send_message.side_effect = [RetryAfter(timedelta(seconds=4)), update(900).message]
        with pytest.warns(PTBDeprecationWarning):
            asyncio.run(TelegramIO(bot, repo, 7).send_pending())
    sleep.assert_awaited_once_with(4)
    assert repo.pending_notices() == []


def test_retry_after_at_limit_still_waits_and_preserves_notice(repo, bot, sleep):
    pending = notice(repo)
    bot.send_message.side_effect = RetryAfter(5)
    asyncio.run(TelegramIO(bot, repo, 7).send_pending())
    assert bot.send_message.call_count == 3
    assert [c.args[0] for c in sleep.call_args_list] == [5, 5, 5]
    assert repo.pending_notices() == [pending]


def test_outbox_never_sends_to_other_chat(repo, bot):
    blocked = notice(repo, chat=-123)
    allowed = notice(repo, number=2)
    asyncio.run(TelegramIO(bot, repo, 7).send_pending())
    assert [c.kwargs["chat_id"] for c in bot.send_message.call_args_list] == [7]
    assert repo.pending_notices() == [blocked]
    assert allowed not in repo.pending_notices()


def test_permanent_error_preserves_notice_but_does_not_block_others(repo, bot):
    blocked = notice(repo)
    notice(repo, number=2)
    bot.send_message.side_effect = [BadRequest("sensitive error"), update(900).message]
    asyncio.run(TelegramIO(bot, repo, 7).send_pending())
    assert bot.send_message.call_count == 2
    assert repo.pending_notices() == [blocked]


def test_crash_after_send_before_mark_does_not_lose_or_duplicate_order(repo, bot):
    repo.ingest_batch([IncomingMessage(update_id=1, user_id=7, chat_id=7, text="add")], 2)
    repo.apply_intent(1, Intent(action="add", lines=[IntentLine(description="arroz", quantity=2)]),
                      "dry_run")
    repo.ingest_batch([IncomingMessage(update_id=2, user_id=7, chat_id=7, text="buy")], 3)
    reply = repo.apply_intent(2, Intent(action="buy"), "dry_run")
    snapshot = repo.get_order(reply.order_id)
    with sqlite3.connect(repo.path) as db:
        db.executescript("""CREATE TRIGGER fail_mark BEFORE UPDATE ON outbox
            BEGIN SELECT RAISE(ABORT, 'injected'); END;""")
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        asyncio.run(TelegramIO(bot, repo, 7).send_pending())
    assert len(repo.pending_notices()) == 2
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER fail_mark")
    reopened = Repository(repo.path)
    asyncio.run(TelegramIO(bot, reopened, 7).send_pending())
    assert reopened.pending_notices() == []
    assert reopened.get_order(reply.order_id) == snapshot
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM orders").fetchone()[0] == 1


def test_long_notice_is_not_truncated_and_partial_failure_stays_pending(repo, bot):
    text = "😀" * 5000
    pending = notice(repo, text=text)
    bot.send_message.side_effect = [update(900).message, BadRequest("injected")]
    asyncio.run(TelegramIO(bot, repo, 7).send_pending())
    assert repo.pending_notices() == [pending]
    bot.send_message.reset_mock(side_effect=True)
    asyncio.run(TelegramIO(bot, repo, 7).send_pending())
    chunks = [c.kwargs["text"] for c in bot.send_message.call_args_list]
    assert "".join(chunks) == text
    assert all(len(c.encode("utf-16-le")) // 2 <= 4096 for c in chunks)
    assert repo.pending_notices() == []


def test_cancellation_preserves_notice(repo, bot):
    pending = notice(repo)
    bot.send_message.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(TelegramIO(bot, repo, 7).send_pending())
    assert repo.pending_notices() == [pending]


@pytest.mark.parametrize("allowed", [True, "7", 0, -7])
def test_invalid_authorized_user_fails_closed(repo, bot, allowed):
    with pytest.raises(ValueError, match="positive integer"):
        TelegramIO(bot, repo, allowed)
    bot.get_updates.assert_not_called()
    bot.send_message.assert_not_called()


def test_poll_timeout_preserves_committed_offset_and_pending_messages(repo, bot):
    bot.get_updates.return_value = (update(1),)
    io = TelegramIO(bot, repo, 7)
    asyncio.run(io.poll_once())
    bot.get_updates.side_effect = TimedOut()
    with pytest.raises(TimedOut):
        asyncio.run(io.poll_once())
    assert repo.telegram_offset() == 2
    assert [m.update_id for m in repo.pending_messages()] == [1]


@pytest.mark.parametrize("metadata", [
    {"forward_origin": {"type": "user", "date": 1, "sender_user": {
        "id": 99, "is_bot": True, "first_name": "Relay"}}},
    {"forward_origin": {"type": "hidden_user", "date": 1, "sender_user_name": "Hidden"}},
    {"quote": {"text": "/comprar", "position": 0, "is_manual": True}},
    {"entities": [{"type": "blockquote", "offset": 0, "length": 8}]},
    {"entities": [{"type": "expandable_blockquote", "offset": 0, "length": 8}]},
    {"via_bot": {"id": 99, "is_bot": True, "first_name": "Relay"}},
    {"sender_business_bot": {"id": 99, "is_bot": True, "first_name": "Relay"}},
    {"from": {"id": 7, "is_bot": True, "first_name": "Bot"}},
    {"is_automatic_forward": True},
    {"sender_chat": {"id": -99, "type": "channel", "title": "Relay"}},
], ids=["forwarded-bot", "hidden-forward", "quote", "blockquote", "expandable-blockquote",
        "via-bot", "business-bot", "bot-sender", "automatic-forward", "sender-chat"])
def test_relayed_or_quoted_commands_are_not_executable(repo, bot, metadata):
    bot.get_updates.return_value = (update(1, text="/comprar", **metadata),)
    asyncio.run(TelegramIO(bot, repo, 7).poll_once())
    reopened = Repository(repo.path)
    assert reopened.pending_messages() == []
    assert reopened.telegram_offset() == 2
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM inbox").fetchone()[0] == 0
    bot.get_updates.return_value = ()
    asyncio.run(TelegramIO(bot, reopened, 7).poll_once())
    assert bot.get_updates.call_args.kwargs["offset"] == 2


def test_direct_command_and_rejected_quote_share_atomic_offset(repo, bot):
    direct = update(1, text="/comprar", entities=[{
        "type": "bot_command", "offset": 0, "length": 8}])
    quoted = update(2, text="/comprar", entities=[{
        "type": "blockquote", "offset": 0, "length": 8}])
    bot.get_updates.return_value = (direct, quoted)
    with sqlite3.connect(repo.path) as db:
        db.executescript("""CREATE TRIGGER fail_offset BEFORE UPDATE ON meta
            BEGIN SELECT RAISE(ABORT, 'injected'); END;""")
    io = TelegramIO(bot, repo, 7)
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        asyncio.run(io.poll_once())
    assert repo.pending_messages() == []
    assert repo.telegram_offset() == 0
    with sqlite3.connect(repo.path) as db:
        db.execute("DROP TRIGGER fail_offset")
    asyncio.run(io.poll_once())
    assert [c.kwargs["offset"] for c in bot.get_updates.call_args_list] == [0, 0]
    reopened = Repository(repo.path)
    assert reopened.pending_messages() == [
        IncomingMessage(update_id=1, user_id=7, chat_id=7, text="/comprar")]
    assert reopened.telegram_offset() == 3
    bot.get_updates.return_value = ()
    asyncio.run(TelegramIO(bot, reopened, 7).poll_once())
    assert bot.get_updates.call_args.kwargs["offset"] == 3


def test_real_bot_serializes_plain_text_and_durable_poll_offset(repo):
    class Transport(BaseRequest):
        def __init__(self):
            self.calls = []

        @property
        def read_timeout(self):
            return 5

        async def initialize(self):
            pass

        async def shutdown(self):
            pass

        async def do_request(self, url, method, request_data=None, **timeouts):
            endpoint = url.rsplit("/", 1)[-1]
            data = request_data.parameters if request_data else {}
            self.calls.append((endpoint, data, timeouts))
            if endpoint == "getMe":
                result = {"id": 123, "is_bot": True, "first_name": "Test", "username": "test_bot"}
            elif endpoint == "getUpdates":
                result = [update(1, text="<i>literal</i>").to_dict()]
            else:
                result = update(9, text=data["text"]).message.to_dict()
            return 200, json.dumps({"ok": True, "result": result}).encode()

    async def exercise():
        transport = Transport()
        async with Bot("123:FAKE_TEST_TOKEN", request=transport,
                       get_updates_request=transport) as real_bot:
            io = TelegramIO(real_bot, repo, 7)
            await io.poll_once()
            repo.apply_intent(1, Intent(action="clarify", question="<i>literal</i>"), "dry_run")
            await io.send_pending()
            await io.poll_once()
        return transport.calls

    calls = asyncio.run(exercise())
    polls = [call for call in calls if call[0] == "getUpdates"]
    assert [call[1]["offset"] for call in polls] == [0, 2]
    assert polls[0][1]["allowed_updates"] == ["message", "callback_query"]
    assert polls[0][2]["read_timeout"] == 35
    sent = next(call[1] for call in calls if call[0] == "sendMessage")
    assert sent["text"] == "<i>literal</i>"
    assert sent["chat_id"] == 7
    assert "parse_mode" not in sent
    assert "entities" not in sent
    assert sent["link_preview_options"] == {"is_disabled": True}
    assert repo.pending_notices() == []
