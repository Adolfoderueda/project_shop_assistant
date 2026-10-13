"""Doctor must inspect synthetic state without changing it."""

import asyncio
import json
import os
import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import cli
import config
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
    monkeypatch.setattr(cli, "load_settings", lambda _root, **_kwargs: settings)

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


def test_doctor_does_not_resecure_private_tree(tmp_path, monkeypatch):
    from storage import Repository

    settings = Settings(telegram_token="synthetic-token", authorized_user_id=123,
                        address="synthetic address", database_path=Path("private/assistant.db"))
    config.save_settings(tmp_path, settings)
    repo = Repository(tmp_path / settings.database_path)
    repo.migrate()
    # The fixture creates a new database after save_settings secured the tree.
    # Secure that synthetic file before testing that doctor leaves it untouched.
    config._private_tree(tmp_path / "private")

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
    monkeypatch.setattr(config, "_private_tree",
                        lambda _path: pytest.fail("doctor must not resecure private files"))

    assert asyncio.run(cli.doctor(tmp_path)) is True


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL integration")
def test_doctor_rejects_foreign_acl_without_repairing_it(tmp_path, monkeypatch):
    settings = Settings(telegram_token="synthetic-token", authorized_user_id=123,
                        address="synthetic address", database_path=Path("private/assistant.db"))
    config.save_settings(tmp_path, settings)
    target = tmp_path / "private" / "settings.json"
    subprocess.run(["icacls", str(target), "/grant", "*S-1-1-0:R"],
                   capture_output=True, check=True)
    read = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", config._READ_ACL]
    env = {**os.environ, "SHOP_ASSISTANT_ACL_PATH": str(target)}
    before = json.loads(subprocess.run(read, env=env, capture_output=True,
                                       text=True, check=True).stdout)

    async def forbidden_get_me():
        pytest.fail("doctor must reject unsafe configuration before Telegram")

    monkeypatch.setattr("telegram.Bot", lambda _token: SimpleNamespace(get_me=forbidden_get_me))
    assert asyncio.run(cli.doctor(tmp_path)) is False
    after = json.loads(subprocess.run(read, env=env, capture_output=True,
                                      text=True, check=True).stdout)
    assert before == after
    assert "S-1-1-0" in {rule["sid"] for rule in after["rules"]}
