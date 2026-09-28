"""Single-owner durable worker. Never log message bodies, settings or adapter errors."""

import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import Settings

logger = logging.getLogger(__name__)


class ProcessLock:
    """OS file lock, held for the worker's entire lifetime (including recovery)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                if not self.file.read(1):
                    self.file.write(b"0")
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            self.file = None
            raise RuntimeError("Worker already running; second process cannot start") from None
        return self

    def __exit__(self, *_):
        if self.file is not None:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_UN)
            self.file.close()


def configure_logging(settings: Settings):
    """Allowlist only our controlled lifecycle records, never third-party HTTP traces."""
    settings.logs_path.mkdir(parents=True, exist_ok=True)
    from config import _private
    _private(settings.logs_path)
    handler = RotatingFileHandler(settings.logs_path / "worker.log", maxBytes=1_000_000,
                                  backupCount=3, encoding="utf-8")
    _private(settings.logs_path / "worker.log")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    for name in ("runtime", "telegram_io"):
        target = logging.getLogger(name)
        target.setLevel(logging.INFO)
        target.propagate = False
        for old in target.handlers[:]:
            target.removeHandler(old)
            old.close()
        target.addHandler(handler)


class _CommandsOnly:
    async def parse(self, text, lines):
        from interpreter import clarify
        return clarify("Interpretación libre desactivada: configura el modelo o usa comandos explícitos.")


async def run(settings: Settings, *, repo=None, recovery=None, checkout=None,
              transport=None, conversation=None, sleep=asyncio.sleep) -> None:
    """Recover first, then dispatch durable inbox/orders/outbox and poll continuously.

    Cancellation does not acknowledge unfinished inbox entries, orders or notices.
    """
    from checkout import CheckoutService
    from conversation import Conversation
    from domain import Destination
    from recovery import Recovery
    from storage import Repository
    from telegram_io import TelegramIO

    with ProcessLock(settings.database_path.parent / "worker.lock"):
        repo = repo or Repository(settings.database_path)
        repo.migrate()
        manager = None
        try:
            if recovery is None or checkout is None:
                from stores.browser import BrowserManager
                from stores.connections import registrations
                from stores.registry import StoreRegistry
                registry = StoreRegistry(registrations())
                manager = BrowserManager(settings.profiles_path, registry)
                for store_id, adapter in registry.adapters.items():
                    adapter.context = await manager.open(store_id)
                stores = registry.adapters
                recovery = recovery or Recovery(repo, stores)
                checkout = checkout or CheckoutService(
                    repo, stores, Destination(postcode=settings.postcode, address=settings.address))
            if transport is None:
                from telegram import Bot
                transport = TelegramIO(Bot(settings.telegram_token.get_secret_value()),
                                       repo, settings.authorized_user_id)
            if conversation is None:
                interpreter = _CommandsOnly()
                if settings.openai_api_key and settings.openai_model:
                    from openai import AsyncOpenAI

                    from interpreter import OpenAIInterpreter
                    interpreter = OpenAIInterpreter(
                        AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value()),
                        settings.openai_model)
                else:
                    logger.warning("Model not configured: commands-only mode; use /lista or /anadir")
                conversation = Conversation(repo, interpreter)
            await recovery.recover()  # Abandoned attempts must be reconciled before new work.
            logger.info("Recovery finished; worker ready")
            while True:
                for message in repo.pending_messages():
                    await conversation.handle(message, settings.mode)
                if repo.resumable_orders():
                    await recovery.recover()
                for order_id in repo.pending_orders():
                    await checkout.run(order_id)
                await transport.send_pending()
                await transport.poll_once()
                await sleep(0)
        finally:
            if manager is not None:
                await manager.close()
