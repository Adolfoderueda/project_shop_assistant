import sqlite3
from pathlib import Path

from storage import Repository
from tests.test_agent_storage import NOW, ingest, propose


def test_new_instance_recovers_unsent_review_and_commit(tmp_path):
    path = tmp_path / 'recovery.db'
    repo = Repository(path)
    repo.migrate()
    propose(repo)
    repo = Repository(path)
    ingest(repo, 2, 'sí')
    saved = repo.apply_agent_control(2, now=NOW)
    repo = Repository(path)
    assert repo.apply_agent_control(2, now=NOW) == saved
    assert len(repo.list_lines()) == 2
    assert len(repo.pending_notices()) == 2


def test_v8_migration_preserves_all_old_tables(tmp_path):
    from catalog import PRODUCT_RULES
    from domain import Intent, IntentLine
    from storage import OBSERVED_PRODUCTS
    from tests.dialogue_support import seed_line
    from tests.test_presentation_storage import prepare_add
    repo = Repository(tmp_path / 'v8.db')
    with sqlite3.connect(repo.path) as db:
        for number in range(1, 9):
            db.executescript((Path(__file__).parents[1] / f'migrations/{number:03}.sql').read_text())
        db.executemany('INSERT INTO products VALUES (?,?)', [(r.id, r.model_dump_json()) for r in PRODUCT_RULES])
        db.executemany('INSERT INTO observed_products VALUES (?,?,?,?,?,?,?,?,?)', OBSERVED_PRODUCTS)
    line = seed_line(repo, 'pan', 2)
    ingest(repo, 2, '/comprar')
    repo.apply_intent(2, Intent(action='buy', lines=[IntentLine(line_id=line.id)]), 'dry_run')
    job = prepare_add(repo)
    with sqlite3.connect(repo.path) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        queries = {t: f"SELECT {'update_id,user_id,chat_id,text,completed,reply_json' if t == 'inbox' else '*'} FROM {t}"
                   for t in tables}
        before = {t: db.execute(query).fetchall() for t, query in queries.items()}
        assert all(before[t] for t in ('list_lines', 'orders', 'order_lines', 'reservations', 'execution', 'inbox', 'outbox', 'dialogue_state', 'presentation_jobs'))
    repo.migrate()
    with sqlite3.connect(repo.path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 10
        assert {t: db.execute(query).fetchall() for t, query in queries.items()} == before
    assert repo.complete_agent_reply(11, job.snapshot.fallback) == job.snapshot.fallback
    assert len(repo.list_lines()) == 2


def test_outbox_failure_rolls_back_proposal_review_and_confirmation(tmp_path):
    import pytest
    repo = Repository(tmp_path / 'failure.db')
    repo.migrate()
    ingest(repo, 1, 'arroz y carne')
    with repo._connection(write=True) as db:
        db.execute("CREATE TRIGGER fail_notice BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT,'notice failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        propose(repo)
    assert repo.agent_snapshot(1, now=NOW).proposal is None
    assert repo.message_result(1)[1] is None
    with repo._connection(write=True) as db:
        db.execute('DROP TRIGGER fail_notice')
    propose(repo)
    ingest(repo, 2, 'sí')
    with repo._connection(write=True) as db:
        db.execute("CREATE TRIGGER fail_notice BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT,'notice failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        repo.apply_agent_control(2, now=NOW)
    assert not repo.list_lines()
    assert repo.agent_snapshot(2, now=NOW).proposal.reviewed_update_id == 1


def test_prepared_legacy_job_wins_over_agent_operation(tmp_path):
    from tests.test_presentation_storage import prepare_add
    repo = Repository(tmp_path / 'prepared.db')
    repo.migrate()
    job = prepare_add(repo)
    before = repo.list_lines()
    result = repo.apply_agent_operation(11, 'proponer_altas', {'items': [{'description': 'carne', 'quantity': 4}]}, None, now=NOW)
    assert result.reply == job.snapshot.fallback
    assert repo.list_lines() == before
    assert repo.agent_snapshot(11, now=NOW).proposal is None


def test_exception_after_commit_replays_without_repeating_batch(tmp_path):
    from contextlib import contextmanager

    import pytest
    repo = Repository(tmp_path / 'after-commit.db')
    repo.migrate()
    propose(repo)
    ingest(repo, 2, 'sí')
    connection = repo._connection

    @contextmanager
    def disconnect_after_commit(*, write=False):
        with connection(write=write) as db:
            yield db
        if write:
            raise RuntimeError('caller lost result after commit')

    repo._connection = disconnect_after_commit
    with pytest.raises(RuntimeError):
        repo.apply_agent_control(2, now=NOW)
    recovered = Repository(repo.path)
    assert len(recovered.list_lines()) == 2
    assert recovered.apply_agent_control(2, now=NOW) == recovered.message_result(2)[1]
    assert len(recovered.pending_notices()) == 2
