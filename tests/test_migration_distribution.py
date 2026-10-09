import importlib.resources
import tomllib
from pathlib import Path


def test_all_immutable_migrations_are_explicit_package_resources():
    root = Path(__file__).resolve().parents[1]
    manifest = tomllib.loads((root / 'pyproject.toml').read_text())['tool']['setuptools']
    assert 'migrations' in manifest['packages']
    assert '*.sql' in manifest['package-data']['migrations']
    resources = importlib.resources.files('migrations')
    for number in range(1, 11):
        name = f'{number:03}.sql'
        assert resources.joinpath(name).read_bytes() == (root / 'migrations' / name).read_bytes()


def test_repository_migrates_through_resource_lookup(tmp_path, monkeypatch):
    import storage
    from storage import Repository
    # No sibling directory exists at this simulated installed-module location.
    monkeypatch.setattr(storage, '__file__', str(tmp_path / 'installed' / 'storage.py'))
    repo = Repository(tmp_path / 'resource.db')
    repo.migrate()
    with repo._connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 10
