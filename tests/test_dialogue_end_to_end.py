"""Synthetic runtime/transport integration; never contact Telegram or stores."""

import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from telegram import Update

from tests.dialogue_support import Clock, dialogue_parts, feed, order_count, propose
from tests.fakes import FakeBot
from tests.test_end_to_end import cycles


def test_dialogue_survives_runtime_restart_and_outbox_replay(tmp_path):
    clock = Clock(datetime(2026, 10, 1, tzinfo=UTC))
    bot = FakeBot()
    path = tmp_path / "dialogue.db"
    parts, store = dialogue_parts(path, bot, clock, propose("arroz"))
    feed(parts, bot, 1, "necesito arroz")
    feed(parts, bot, 2, "2")
    parts, store2 = dialogue_parts(path, bot, clock, propose("pasta", "mention_product"))
    feed(parts, bot, 3, "ahora pasta")
    feed(parts, bot, 4, "añádelo")
    feed(parts, bot, 5, "3 paquetes")
    parts, store3 = dialogue_parts(path, bot, clock, propose("arroz integral", "mention_product"))
    feed(parts, bot, 6, "ahora arroz integral")
    feed(parts, bot, 7, "sustitúyelo")
    assert parts[1].dialogue_state(7, 7, now=clock()).question == "confirm_replace"
    # Restart while the durable confirmation is pending, before delivery.
    parts, store4 = dialogue_parts(path, bot, clock)
    bot.receive(8, "sí")
    cycles(parts, 1)  # Poll only; leave update pending across another restart.
    parts, store5 = dialogue_parts(path, bot, clock)
    message = parts[1].pending_messages()[0]
    original = asyncio.run(parts[3].handle(message, "dry_run"))
    state = parts[1].dialogue_state(7, 7, now=clock())
    notices = parts[1].pending_notices()
    clock.advance(30)
    assert asyncio.run(parts[3].handle(message, "dry_run")) == original
    assert parts[1].dialogue_state(7, 7, now=clock()) == state
    assert parts[1].pending_notices() == notices
    cycles(parts, 1)  # Deliver the persisted confirmation prompt.
    feed(parts, bot, 9, "conserva la cantidad")
    assert [(line.description, line.quantity) for line in parts[1].list_lines()] == [
        ("arroz", 2), ("arroz integral", 3),
    ]
    assert parts[1].pending_notices() == []
    assert any("arroz integral" in text and "3 envases" in text for _, text in bot.sent)
    rows = parts[1].list_lines()
    state = parts[1].dialogue_state(7, 7, now=clock())
    message, original = parts[1].message_result(9)
    clock.advance(30)
    assert asyncio.run(parts[3].handle(message, "dry_run")) == original
    assert parts[1].list_lines() == rows
    assert parts[1].dialogue_state(7, 7, now=clock()) == state
    assert parts[1].pending_notices() == []
    assert order_count(parts[1]) == 0
    assert all(s.quote_calls == s.prepare_calls == s.submit_calls == 0
               for s in (store, store2, store3, store4, store5))


def test_expired_restart_does_not_consume_number_as_selection(tmp_path):
    clock = Clock(datetime(2026, 10, 1, tzinfo=UTC))
    bot = FakeBot()
    path = tmp_path / "dialogue.db"
    parts, _ = dialogue_parts(path, bot, clock, propose("arroz"))
    feed(parts, bot, 1, "necesito arroz")
    before = parts[1].list_lines()
    clock.advance(900)
    parts, _ = dialogue_parts(path, bot, clock)
    feed(parts, bot, 2, "2")
    assert parts[1].list_lines() == before
    assert parts[1].dialogue_state(7, 7, now=clock()) is None
    parts, _ = dialogue_parts(path, bot, clock, propose("pasta"))
    feed(parts, bot, 3, "necesito pasta")
    feed(parts, bot, 4, "4")
    assert [(l.description, l.quantity) for l in parts[1].list_lines()] == [("arroz", None), ("pasta", 4)]
    assert order_count(parts[1]) == 0


def test_model_failure_keeps_commands_and_contextual_answers_available(tmp_path):
    class FailedModel:
        async def parse(self, text, lines):
            raise RuntimeError("synthetic model failure")

    clock = Clock(datetime(2026, 10, 1, tzinfo=UTC))
    bot = FakeBot()
    parts, store = dialogue_parts(tmp_path / "dialogue.db", bot, clock, FailedModel())
    feed(parts, bot, 1, "/anadir arroz")
    before = parts[1].list_lines()
    state = parts[1].dialogue_state(7, 7, now=clock())
    clock.advance(30)
    feed(parts, bot, 2, "ahora pasta")
    assert parts[1].list_lines() == before
    assert parts[1].dialogue_state(7, 7, now=clock()) == state
    assert parts[1].product_requests() == []
    feed(parts, bot, 3, "/lista")
    assert before[0].id in bot.sent[-1][1]
    feed(parts, bot, 4, "2")
    assert parts[1].list_lines()[0].quantity == 2
    assert order_count(parts[1]) == 0
    assert store.quote_calls == store.prepare_calls == store.submit_calls == 0


def test_foreign_chat_never_consumes_owner_context(tmp_path):
    clock = Clock(datetime(2026, 10, 1, tzinfo=UTC))
    bot = FakeBot()
    parts, _ = dialogue_parts(tmp_path / "dialogue.db", bot, clock)
    feed(parts, bot, 1, "/anadir arroz")
    before = parts[1].list_lines()
    state = parts[1].dialogue_state(7, 7, now=clock())
    sent = list(bot.sent)
    bot.receive(2, "2", user_id=8)
    bot.receive(3, "sí", user_id=8)
    bot.receive(4, "2")
    relayed = bot.updates[-1].to_dict()
    relayed["message"]["chat"]["id"] = 8
    bot.updates[-1] = Update.de_json(relayed, None)
    cycles(parts, 2)
    assert parts[1].list_lines() == before
    assert parts[1].dialogue_state(7, 7, now=clock()) == state
    with pytest.raises(KeyError):
        parts[1].message_result(2)
    with pytest.raises(KeyError):
        parts[1].message_result(3)
    with pytest.raises(KeyError):
        parts[1].message_result(4)
    assert bot.sent == sent
    assert order_count(parts[1]) == 0


def test_replacement_and_context_roll_back_when_outbox_rejects(tmp_path):
    clock = Clock(datetime(2026, 10, 1, tzinfo=UTC))
    bot = FakeBot()
    parts, _ = dialogue_parts(tmp_path / "dialogue.db", bot, clock, propose("pasta", "mention_product"))
    feed(parts, bot, 1, "/anadir 2 arroz")
    feed(parts, bot, 2, "ahora pasta")
    feed(parts, bot, 3, "sustitúyelo")
    feed(parts, bot, 4, "sí")
    before = parts[1].list_lines()
    state = parts[1].dialogue_state(7, 7, now=clock())
    bot.receive(5, "3 paquetes")
    cycles(parts, 1)
    with sqlite3.connect(parts[1].path) as db:
        db.executescript("CREATE TRIGGER reject_notice BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'injected'); END;")
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        cycles(parts, 1)
    assert parts[1].list_lines() == before
    assert parts[1].dialogue_state(7, 7, now=clock()) == state
    assert parts[1].message_result(5)[1] is None
    assert parts[1].pending_notices() == []
    with sqlite3.connect(parts[1].path) as db:
        db.execute("DROP TRIGGER reject_notice")
    cycles(parts, 1)
    assert [(line.description, line.quantity) for line in parts[1].list_lines()] == [("pasta", 3)]
    assert order_count(parts[1]) == 0


@pytest.mark.skipif(os.name != "nt" or not shutil.which("powershell.exe"), reason="Windows probe")
@pytest.mark.parametrize("fail,code", [(False, 0), (True, 1)])
def test_probe_exit_and_isolated_cleanup(tmp_path, fail, code):
    # A private-data sentinel must remain untouched; the probe never loads it.
    private = tmp_path / "private"
    private.mkdir()
    sentinel = private / "settings.json"
    sentinel.write_text("do not load", encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "Probe-Dialogue.ps1"
    command = ["powershell.exe", "-NoProfile", "-File", str(script),
               "-Python", sys.executable, "-Offline"]
    if fail:
        command.append("-FailExpectation")
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == code, result.stdout + result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    assert records[-1]["status"] == ("FAIL" if fail else "PASS")
    assert records[-1]["failures"] == (["offline injected expectation failure"] if fail else [])
    steps = [record for record in records if "case" in record]
    assert len(steps) == 25
    assert all(record["passed"] and record["orders"] == 0 for record in steps)
    root = Path(records[0]["temporary_root"])
    approved = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "opencode"
    assert root.parent == approved
    assert not root.exists()
    assert sentinel.read_text(encoding="utf-8") == "do not load"
    assert list(tmp_path.iterdir()) == [private]
