"""Offline runtime safety and lifecycle contracts."""

import asyncio
import logging
import subprocess
import sys

import pytest

from config import Settings, load_settings
from runtime import ProcessLock, run


def settings(tmp_path):
    return Settings(telegram_token="secret-token", authorized_user_id=123,
                    address="private destination", database_path=tmp_path / "assistant.db",
                    logs_path=tmp_path / "private" / "logs",
                    profiles_path=tmp_path / "private" / "profiles")


def test_missing_configuration_has_actionable_message(tmp_path):
    with pytest.raises(ValueError, match="configure"):
        load_settings(tmp_path)


def test_second_process_cannot_start(tmp_path):
    with (ProcessLock(tmp_path / "worker.lock"),
          pytest.raises(RuntimeError, match="already running"),
          ProcessLock(tmp_path / "worker.lock")):
        pytest.fail("second worker entered")
    with ProcessLock(tmp_path / "worker.lock"):
        pass


def test_separate_process_does_not_enter_worker(tmp_path):
    lock = tmp_path / "worker.lock"
    code = ("from runtime import ProcessLock\n"
            "import sys\n"
            "try:\n"
            "    with ProcessLock(sys.argv[1]):\n"
            "        sys.exit(99)\n"
            "except RuntimeError:\n"
            "    sys.exit(42)\n")
    with ProcessLock(lock):
        result = subprocess.run([sys.executable, "-c", code, str(lock)],
                                capture_output=True, timeout=10, check=False)
    assert result.returncode == 42


def test_restart_recovers_before_new_checkout(tmp_path):
    events = []

    class Repo:
        def migrate(self): events.append("migrate")
        def pending_messages(self): return []
        def pending_orders(self): return ["new"]
        def resumable_orders(self): return []

    class Recovery:
        async def recover(self): events.append("recover")

    class Checkout:
        async def run(self, order_id): events.append("checkout:" + order_id)

    class IO:
        async def poll_once(self): events.append("poll")
        async def send_pending(self): events.append("outbox")

    async def stop_after_cycle(_):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(settings(tmp_path), repo=Repo(), recovery=Recovery(),
                        checkout=Checkout(), transport=IO(), sleep=stop_after_cycle))
    assert events.index("recover") < events.index("checkout:new")
    assert events.index("recover") < events.index("poll")


def test_shutdown_preserves_pending_work(tmp_path):
    from domain import IncomingMessage
    from storage import Repository

    repo = Repository(tmp_path / "assistant.db")
    repo.migrate()
    msg = IncomingMessage(update_id=1, user_id=123, chat_id=123, text="/lista")
    repo.ingest_batch([msg], 2)

    class Recovery:
        async def recover(self): pass

    class IO:
        async def poll_once(self): pass
        async def send_pending(self): pass

    class Conversation:
        async def handle(self, message, mode): raise asyncio.CancelledError

    class Checkout:
        async def run(self, order_id): pass

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(settings(tmp_path), repo=repo, recovery=Recovery(), transport=IO(),
                        conversation=Conversation(), checkout=Checkout()))
    assert repo.pending_messages() == [msg]


def test_logs_redact_secrets(tmp_path, caplog):
    from runtime import configure_logging
    settings_ = settings(tmp_path)
    configure_logging(settings_)
    with caplog.at_level(logging.INFO, logger="runtime"):
        logging.getLogger("runtime").info("Worker started")
    log = (tmp_path / "private" / "logs" / "worker.log").read_text(encoding="utf-8")
    assert "Worker started" in log
    assert "secret-token" not in log
    assert "private destination" not in log
    assert "secret-token" not in caplog.text
    assert "private destination" not in caplog.text


def test_configuration_private_and_default_dry_run(tmp_path):
    from config import save_settings

    save_settings(tmp_path, settings(tmp_path).model_copy(update={"database_path":
                                                              tmp_path / "private" / "assistant.db"}))
    loaded = load_settings(tmp_path)
    assert loaded.mode == "dry_run"
    assert loaded.authorized_user_id == 123
    assert loaded.database_path == (tmp_path / "private" / "assistant.db").resolve()
    assert "secret-token" not in repr(loaded)


def test_binding_ignores_old_and_foreign_chats():
    from types import SimpleNamespace

    from cli import bind_user

    def update(id, uid, chat, text):
        user = SimpleNamespace(id=uid, is_bot=False)
        message = SimpleNamespace(text=text, from_user=user,
                                  chat=SimpleNamespace(id=chat, type="private"),
                                  forward_origin=None, via_bot=None, sender_chat=None,
                                  sender_business_bot=None, quote=None,
                                  is_automatic_forward=False)
        return SimpleNamespace(update_id=id, message=message)

    class Bot:
        def __init__(self): self.offsets = []
        async def get_updates(self, *, offset=None, **_):
            self.offsets.append(offset)
            if offset is None:
                return [update(5, 123, 123, "/start nonce")]
            return [update(6, 123, 999, "/start nonce"),
                    update(7, 123, 123, "/start nonce")]

    bot = Bot()
    assert asyncio.run(bind_user(bot, "nonce")) == (123, 8)
    assert bot.offsets == [None, 6]
