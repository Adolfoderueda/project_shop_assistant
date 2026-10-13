"""Check an installed wheel without importing application code from the checkout.

Run with python -P, PYTHONPATH pointing only at the wheel installation, and a
working directory outside the source tree. This never loads private settings.
"""

import argparse
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed-root', required=True, type=Path)
    target = parser.parse_args().installed_root.resolve()
    for name in ('storage', 'runtime', 'telegram_io', 'cli', 'shopping_agent.skills'):
        module = importlib.import_module(name)
        if not Path(module.__file__).resolve().is_relative_to(target):
            raise AssertionError(f'{name} was imported from outside the installed wheel')

    from shopping_agent.skills import load_skills
    from storage import Repository

    if not load_skills().strip():
        raise AssertionError('Installed skill resources are empty')
    with TemporaryDirectory(prefix='wheel-smoke-', dir=target.parent) as directory:
        repo = Repository(Path(directory) / 'synthetic.db')
        repo.migrate()
        repo.migrate()
        with repo._connection() as db:
            assert db.execute('PRAGMA user_version').fetchone()[0] == 10
            assert db.execute('SELECT count(*) FROM list_lines').fetchone()[0] == 0
        assert repo.list_lines() == []
    print('PASS: installed imports, skills, schema 10 and repeat migration')


if __name__ == '__main__':
    main()
