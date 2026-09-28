"""Offline Bot → TelegramIO → Conversation → Checkout/Recovery → Bot."""

import asyncio

import pytest

from checkout import CheckoutService
from config import Settings
from conversation import Conversation
from domain import Destination, Intent, IntentLine
from recovery import Recovery
from runtime import run
from storage import Repository
from telegram_io import TelegramIO
from tests.factories import offer
from tests.fakes import FakeBot, FakeInterpreter, FakeStore


def components(path, bot, store, mode="dry_run"):
    repo = Repository(path)
    repo.migrate()
    settings = Settings(telegram_token="offline-test", authorized_user_id=7,
                        address="test address", database_path=path, mode=mode)
    destination = Destination(postcode="28023", address="test address")
    interpreter = FakeInterpreter(Intent(action="add", lines=[IntentLine(description="pienso")]))
    return (settings, repo, TelegramIO(bot, repo, 7), Conversation(repo, interpreter),
            CheckoutService(repo, {store.store_id: store}, destination),
            Recovery(repo, {store.store_id: store}))


def cycles(parts, count):
    settings, repo, transport, conversation, checkout, recovery = parts
    remaining = count

    async def stop(_):
        nonlocal remaining
        remaining -= 1
        if remaining == 0:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(settings, repo=repo, recovery=recovery, checkout=checkout,
                        transport=transport, conversation=conversation, sleep=stop))


def start_order(path, bot, store, mode, *, defer_purchase=False):
    bot.receive(1, "quiero pienso")
    cycles(components(path, bot, store, mode), 2)
    repo = Repository(path)
    line = repo.list_lines()[0]
    assert line.product_id == "dog-food"
    bot.receive(2, f"/cantidad {line.id} 2")
    bot.receive(3, "/comprar")
    cycles(components(path, bot, store, mode), 1 if defer_purchase else 2)
    return repo, line


def test_telegram_to_simulated_receipt_after_restart(tmp_path):
    path = tmp_path / "assistant.db"
    bot = FakeBot()
    store = FakeStore("test", [offer()])
    repo, line = start_order(path, bot, store, "dry_run", defer_purchase=True)
    assert len(repo.list_lines()) == 1
    assert repo.list_lines()[0].quantity is None
    assert not any("simulado" in text.lower() for _, text in bot.sent)
    # Restart with fresh persistence/service objects and deliver the durable receipt.
    cycles(components(path, bot, store), 2)
    assert store.submit_calls == store.prepare_calls == 0
    assert len(repo.list_lines()) == 1
    assert repo.list_lines()[0].id == line.id
    assert repo.list_lines()[0].quantity == 2
    order_id = repo.message_result(3)[1].order_id
    assert repo.order_status(order_id) == "simulado"
    assert any("simulado" in text.lower() for _, text in bot.sent)
    assert not any("pedido confirmado" in text.lower() for _, text in bot.sent)


def test_confirmed_order_is_not_repeated_after_crash(tmp_path):
    path = tmp_path / "assistant.db"
    bot = FakeBot()
    store = FakeStore("test", [offer()])
    repo, _ = start_order(path, bot, store, "live", defer_purchase=True)
    interrupted = []

    def crash_after_external_commit(attempt_id):
        assert attempt_id in store.ledger
        interrupted.append(attempt_id)
        # CancelledError is BaseException, not caught by checkout's Exception
        # handler: model a worker dying before recording any local response.
        raise asyncio.CancelledError

    store.after_commit = crash_after_external_commit
    cycles(components(path, bot, store, "live"), 2)
    assert len(interrupted) == 1
    assert store.submit_calls == 1
    assert len(store.ledger) == 1
    order_id = repo.message_result(3)[1].order_id
    assert repo.order_status(order_id) != "confirmado"
    assert [attempt for attempt, _ in repo.uncertain_attempts()] == interrupted
    assert repo.list_lines()[0].quantity == 2
    store.after_commit = None
    cycles(components(path, bot, store, "live"), 2)
    assert store.submit_calls == 1
    assert repo.order_status(order_id) == "confirmado"
    assert repo.list_lines() == []
    assert len(store.ledger) == 1
    assert any("confirmado" in text.lower() for _, text in bot.sent)


def test_unknown_reconciliation_never_repeats_submit(tmp_path):
    path = tmp_path / "assistant.db"
    bot = FakeBot()
    store = FakeStore("test", [offer()])
    store.lose_response = True
    repo, _ = start_order(path, bot, store, "live")
    store.ledger.clear()  # Fake has no definitive external evidence either way.
    cycles(components(path, bot, store, "live"), 2)
    assert store.submit_calls == 1
    assert repo.order_status(repo.message_result(3)[1].order_id) == "resultado_incierto"
    assert len(repo.list_lines()) == 1
    assert len(repo.uncertain_attempts()) == 1
    assert not any("pedido confirmado" in text.lower() for _, text in bot.sent)
