"""Synthetic databases only: migration must preserve literal historical rows."""

import sqlite3
from pathlib import Path

import pytest

from storage import Repository


def seeded_v9_repo(tmp_path):
    repo = Repository(tmp_path / 'synthetic.db')
    with sqlite3.connect(repo.path) as db:
        for version in range(1, 10):
            db.executescript((Path(__file__).parents[1] / f'migrations/{version:03}.sql').read_text())
        db.execute("INSERT INTO inbox VALUES (1,7,7,'original',1,?)",
                   ('{"text":"old reply","order_id":null}',))
        db.execute("INSERT INTO outbox VALUES ('notice',1,7,?,NULL,'old timestamp')",
                   ('{"text":"old reply","order_id":null}',))
        db.execute("INSERT INTO list_lines VALUES ('unknown',NULL,'huevos',NULL,1,1)")
        db.execute("INSERT INTO orders VALUES ('order','dry_run',1,'old order timestamp')")
        db.execute("INSERT INTO order_lines VALUES ('order',0,?)",
                   (('{"id":"unknown","product_id":null,"description":"huevos",'
                     '"quantity":null,"revision":1}'),))
    return repo


def historical_rows(repo):
    queries = (
        'SELECT update_id,user_id,chat_id,text,completed,reply_json FROM inbox ORDER BY update_id',
        'SELECT id,update_id,chat_id,reply_json,sent_at,created_at FROM outbox ORDER BY id',
        'SELECT id,product_id,description,quantity,revision,source_update_id FROM list_lines ORDER BY id',
        'SELECT id,mode,source_update_id,created_at FROM orders ORDER BY id',
        'SELECT order_id,position,line_json FROM order_lines ORDER BY order_id,position',
    )
    with sqlite3.connect(repo.path) as db:
        return tuple(db.execute(query).fetchall() for query in queries)


@pytest.mark.parametrize('old', [False, True])
def test_migration_preserves_old_unknown_quantity_and_reply(tmp_path, old):
    repo = seeded_v9_repo(tmp_path) if old else Repository(tmp_path / 'empty.db')
    before = historical_rows(repo) if old else None
    repo.migrate()
    with repo._connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 10
        assert {'guided_questions', 'guided_topics', 'guided_tokens', 'telegram_deliveries'} <= {
            row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if old:
            assert tuple(db.execute('SELECT kind,payload_json,callback_query_id,callback_ack_state '
                                    'FROM inbox').fetchone()) == ('message', None, None, None)
    if old:
        assert historical_rows(repo) == before
        assert repo.message_result(1)[1].keyboard is None


@pytest.mark.parametrize('old', [False, True])
def test_migration_rollback_includes_tables_and_columns(tmp_path, monkeypatch, old):
    repo = seeded_v9_repo(tmp_path) if old else Repository(tmp_path / 'empty.db')
    before = historical_rows(repo) if old else None
    original = Path.read_text

    def interrupted(path, *args, **kwargs):
        text = original(path, *args, **kwargs)
        if path.name == '010.sql':
            return text.replace('PRAGMA user_version = 10;', 'INSERT INTO missing_table VALUES (1);')
        return text

    monkeypatch.setattr(Path, 'read_text', interrupted)
    with pytest.raises(sqlite3.OperationalError):
        repo.migrate()
    with repo._connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == (9 if old else 0)
        assert 'kind' not in {row[1] for row in db.execute('PRAGMA table_info(inbox)')}
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'guided_%' "
                              "OR name='telegram_deliveries'").fetchall()
        if not old:
            assert not db.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchall()
    if old:
        assert historical_rows(repo) == before


def test_v11_rejected(tmp_path):
    repo = seeded_v9_repo(tmp_path)
    with repo._connection() as db:
        db.execute('PRAGMA user_version=11')
    with pytest.raises(ValueError, match='newer'):
        repo.migrate()
