import asyncio

import pytest

from config import Settings
from domain import IncomingMessage, Intent, IntentLine
from runtime import run
from tests.dialogue_support import make_repo, order_count
from tests.fakes import FakeBot, FakeInterpreter
from tests.test_reply_conversation import Writer


class Recovery:
    async def recover(self):
        pass


class Checkout:
    async def run(self, _):
        pytest.fail("unexpected checkout/store access")


def configured(repo, provider="ollama", uid=7):
    return Settings(telegram_token="synthetic-token", authorized_user_id=uid,
                    address="synthetic destination", database_path=repo.path,
                    model_provider=provider)


async def stop(_):
    raise asyncio.CancelledError


@pytest.mark.parametrize("provider", ["ollama", "commands_only", "openai"])
def test_fake_runtime_does_not_call_stores_or_orders(tmp_path, monkeypatch, provider):
    import ollama_interpreter
    import ollama_replies
    from telegram_io import TelegramIO

    repo = make_repo(tmp_path)
    repo.ingest_batch([IncomingMessage(update_id=10, user_id=7, chat_id=7,
                                       text="necesito arroz")], 11)
    writer = Writer()
    models = []

    def factory(model):
        models.append(model)
        return writer

    monkeypatch.setattr(ollama_replies, "OllamaReplyWriter", factory)
    monkeypatch.setattr(ollama_interpreter, "OllamaInterpreter", lambda _: FakeInterpreter(
        Intent(action="add", lines=[IntentLine(description="arroz")])))
    bot = FakeBot()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(configured(repo, provider), repo=repo, recovery=Recovery(),
                        checkout=Checkout(), transport=TelegramIO(bot, repo, 7), sleep=stop))
    assert order_count(repo) == 0
    assert repo.message_result(10)[1] is not None
    assert len(models) == len(writer.snapshots) == (1 if provider == "ollama" else 0)
    assert len(bot.sent) == 1
    assert repo.pending_notices() == []


def test_disabled_runtime_recovers_prepared_without_model(tmp_path, monkeypatch):
    import ollama_replies
    from telegram_io import TelegramIO
    from tests.test_presentation_storage import NOW

    repo = make_repo(tmp_path)
    repo.ingest_batch([IncomingMessage(update_id=10, user_id=7, chat_id=7,
                                       text="necesito arroz")], 11)
    job = repo.prepare_dialogue(10, Intent(action="add", lines=[IntentLine(description="arroz")]),
                               "dry_run", now=NOW)
    monkeypatch.setattr(ollama_replies, "OllamaReplyWriter", lambda _: pytest.fail("disabled writer"))
    bot = FakeBot()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(configured(repo, "commands_only"), repo=repo, recovery=Recovery(),
                        checkout=Checkout(), transport=TelegramIO(bot, repo, 7), sleep=stop))
    assert repo.message_result(10)[1] == job.snapshot.fallback
    assert len(repo.list_lines()) == 1 and repo.list_lines()[0].revision == 1
    assert order_count(repo) == 0 and len(bot.sent) == 1


def test_foreign_prepared_owner_rejected_before_draft(tmp_path, monkeypatch):
    import ollama_replies
    from tests.test_presentation_storage import NOW

    repo = make_repo(tmp_path)
    repo.ingest_batch([IncomingMessage(update_id=10, user_id=7, chat_id=7,
                                       text="necesito arroz")], 11)
    repo.prepare_dialogue(10, Intent(action="add", lines=[IntentLine(description="arroz")]),
                          "dry_run", now=NOW)
    monkeypatch.setattr(ollama_replies, "OllamaReplyWriter", lambda _: pytest.fail("foreign writer"))
    with pytest.raises(PermissionError, match="owner"):
        asyncio.run(run(configured(repo, uid=8), repo=repo, recovery=Recovery(),
                        checkout=Checkout(), transport=object(), sleep=stop))
    assert repo.message_result(10)[1] is None and order_count(repo) == 0
