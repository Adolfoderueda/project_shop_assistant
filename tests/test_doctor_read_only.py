"""Doctor must inspect synthetic state without changing it."""

import asyncio
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import cli
from config import Settings


def test_doctor_does_not_upgrade_existing_schema(tmp_path, monkeypatch, capsys):
    database = tmp_path / "assistant.db"
    with sqlite3.connect(database) as connection:
        for number in range(1, 10):
            script = (Path(__file__).parents[1] / "migrations" / f"{number:03}.sql").read_text()
            connection.executescript(script)
        connection.execute("INSERT INTO products VALUES (?, ?)", ("synthetic", "{}"))

    settings = Settings(telegram_token="synthetic-token", authorized_user_id=123,
                        address="synthetic address", database_path=database)
    monkeypatch.setattr(cli, "load_settings", lambda _root: settings)

    class FakeBot:
        def __init__(self, _token):
            pass

        async def get_me(self):
            return SimpleNamespace(id=1)

    class FakePlaywright:
        async def __aenter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(executable_path=__file__))

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr("telegram.Bot", FakeBot)
    monkeypatch.setattr("playwright.async_api.async_playwright", FakePlaywright)
    result = asyncio.run(cli.doctor(tmp_path))

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 9
        assert connection.execute("SELECT id FROM products").fetchall() == [("synthetic",)]
    assert result is False
    assert "SQLite: blocked (schema update required)" in capsys.readouterr().out
