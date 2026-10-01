"""Reusable dialogue test helpers using real temporary SQLite repositories."""

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from conversation import Conversation
from domain import IncomingMessage, Intent, IntentLine, ListLine, Reply, utc
from storage import Repository
from tests.fakes import FakeInterpreter


class Clock:
    def __init__(self, now: datetime):
        self.now = utc(now)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def make_repo(tmp_path: Path) -> Repository:
    repo = Repository(tmp_path / "dialogue.db")
    repo.migrate()
    return repo


def _next_update(repo: Repository) -> int:
    with sqlite3.connect(repo.path) as db:
        return db.execute("SELECT coalesce(max(update_id),0)+1 FROM inbox").fetchone()[0]


def seed_line(
    repo: Repository, description: str, quantity: int | None = None,
) -> ListLine:
    update_id = _next_update(repo)
    message = IncomingMessage(update_id=update_id, user_id=7, chat_id=7, text=description)
    before = {line.id for line in repo.list_lines()}
    repo.ingest_batch([message], update_id + 1)
    repo.apply_intent(update_id, Intent(
        action="add", lines=[IntentLine(description=description, quantity=quantity)],
    ), "dry_run")
    return next(line for line in repo.list_lines() if line.id not in before)


def send(
    repo: Repository, text: str, interpreter=None, *, clock=None, update_id=None, user_id=7,
) -> Reply:
    if update_id is None:
        update_id = _next_update(repo)
    message = IncomingMessage(update_id=update_id, user_id=user_id, chat_id=7, text=text)
    repo.ingest_batch([message], update_id + 1)
    kwargs = {} if clock is None else {"clock": clock}
    conversation = Conversation(repo, interpreter or FakeInterpreter(), **kwargs)
    return asyncio.run(conversation.handle(message, "dry_run"))


def order_count(repo: Repository) -> int:
    with sqlite3.connect(repo.path) as db:
        return db.execute("SELECT count(*) FROM orders").fetchone()[0]


def dialogue_parts(path, bot, clock, interpreter=None):
    from tests.fakes import FakeStore
    from tests.test_end_to_end import components

    store = FakeStore("test", [])
    parts = list(components(path, bot, store))
    parts[3] = Conversation(parts[1], interpreter or FakeInterpreter(), clock=clock)

    async def forbidden(*args, **kwargs):
        raise AssertionError("Dialogue integration must not invoke checkout/store operations")

    parts[4].run = forbidden
    for method in ("search", "quote", "prepare", "submit", "reconcile"):
        setattr(store, method, forbidden)
    return tuple(parts), store


def feed(parts, bot, number, text):
    from tests.test_end_to_end import cycles

    bot.receive(number, text)
    cycles(parts, 2)


def propose(name, action="add"):
    return FakeInterpreter(Intent(action=action, lines=[IntentLine(description=name)]))
