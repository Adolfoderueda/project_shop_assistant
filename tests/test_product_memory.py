import sqlite3
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from domain import Intent
from product_memory import ObservedProduct, _record_missing_product
from storage import Repository
from tests.factories import message


@pytest.fixture
def repo(tmp_path):
    result = Repository(tmp_path / "products.db")
    result.migrate()
    return result


def test_fresh_migration_seeds_only_reviewed_historical_observations(repo):
    with sqlite3.connect(repo.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 9
        assert db.execute("SELECT count(*) FROM observed_products").fetchone()[0] == 4
        assert db.execute("SELECT count(*) FROM products").fetchone()[0] == 3
        assert "gtin" not in {row[1] for row in db.execute("PRAGMA table_info(observed_products)")}
    assert repo.find_products("Alpha Spirit Wild Fish") == [
        ObservedProduct(
            id="amascotados-alpha-spirit-wild-fish-12kg",
            store_id="amascotados",
            product_id="dog-food",
            title="Alpha Spirit Wild Fish 12 Kg",
            url="https://www.amascotados.com/alpha-spirit/2883-alpha-spirit-seco-only-fish-12-kg-8436586310295.html",
            observed_on="2026-09-27",
            price_cents=6399,
            availability=True,
            format_note="12 kg; GTIN no verificado independientemente",
        )
    ]
    with pytest.raises(FrozenInstanceError):
        repo.find_products("Alpha Spirit")[0].price_cents = 1


def test_migrate_twice_preserves_list_offset_and_observations(repo):
    repo.ingest_batch([message()], 2)
    repo.apply_intent(1, Intent(action="add", lines=[{"description": "arroz"}]), "dry_run")
    lines = repo.list_lines()
    repo.migrate()
    assert repo.list_lines() == lines
    assert repo.telegram_offset() == 2
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM observed_products").fetchone()[0] == 4


def test_upgrade_from_v4_preserves_existing_state(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        for number in range(1, 5):
            db.executescript((Path(__file__).parents[1] / f"migrations/{number:03}.sql").read_text())
        db.execute("UPDATE meta SET value=42 WHERE key='telegram_offset'")
        db.commit()
    repo = Repository(path)
    repo.migrate()
    repo.migrate()
    assert repo.telegram_offset() == 42
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 9
        assert db.execute("SELECT count(*) FROM observed_products").fetchone()[0] == 4


def test_search_aliases_accents_boundaries_and_limit(repo):
    results = repo.find_products("pañales Dodot")
    assert {result.store_id for result in results} == {"nappy", "mercadona"}
    assert len(repo.find_products("PANALES DODOT", limit=1)) == 1
    assert repo.find_products("pañales Dodot", limit=0) == []
    assert repo.find_products("arroz") == []
    assert repo.find_products("dodotic") == []
    assert repo.find_products("Blemil")[0].availability is None
    assert repo.find_products("Blemil")[0].format_note == "800 g; referencia no verificada"
    assert repo.find_products("Dodot Sensitive")[0].observed_on == "2026-09-28"
    assert repo.find_products("Dodot Sensitive")[0].availability is None


def test_search_returns_python_boolean_availability_without_inventing_unknown(repo):
    assert repo.find_products("Alpha Spirit")[0].availability is True
    assert repo.find_products("Blemil")[0].availability is None
    with sqlite3.connect(repo.path) as db:
        db.execute("UPDATE observed_products SET availability=0 WHERE store_id='nappy'")
    assert next(
        product.availability for product in repo.find_products("Dodot talla 3")
        if product.store_id == "nappy"
    ) is False


def test_backlog_normalizes_name_and_stores_no_message_text(repo):
    with repo._connection(write=True) as db:
        _record_missing_product(db, " Arroz ")
        _record_missing_product(db, "arroz")
    assert repo.product_requests() == ["arroz"]
    with sqlite3.connect(repo.path) as db:
        rows = db.execute("SELECT * FROM product_requests").fetchall()
        assert len(rows) == 1
        assert "arroz" in rows[0]
        assert any(str(value)[:10] == str(value) and len(str(value)) == 10
                   for value in rows[0] if value != "arroz")
        assert {row[1] for row in db.execute("PRAGMA table_info(product_requests)")} == {
            "name", "requested_on"
        }
