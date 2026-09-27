import sqlite3

import pytest
from pydantic import ValidationError

from catalog import PRODUCT_RULES
from config import Settings
from domain import Intent, IntentLine
from restrictions import validate_product
from storage import Repository
from tests.factories import intent, message, offer


@pytest.fixture
def repo(tmp_path):
    result = Repository(tmp_path / "test.db")
    result.migrate()
    return result


def apply(repo, number, action, **line):
    repo.ingest_batch([message(number)], number + 1)
    return repo.apply_intent(number, intent(action, **line), "dry_run")


def test_batch_and_offset_are_atomic(repo):
    repo.ingest_batch([message()], 2)
    with sqlite3.connect(repo.path) as db:
        db.executescript("""CREATE TRIGGER reject_message BEFORE INSERT ON inbox
        WHEN NEW.update_id = 3 BEGIN SELECT RAISE(ABORT, 'injected'); END;""")
    with pytest.raises(sqlite3.IntegrityError):
        repo.ingest_batch([message(2), message(3)], 4)
    assert repo.telegram_offset() == 2
    assert repo.pending_messages() == [message()]


def test_order_survives_reopen(repo):
    apply(repo, 1, "add", description="Dodot talla 3", quantity=2)
    snapshot = repo.list_lines()
    reply = apply(repo, 2, "buy")
    apply(repo, 3, "set_quantity", line_id=snapshot[0].id, quantity=5)
    reopened = Repository(repo.path)
    reopened.migrate()
    assert reopened.get_order(reply.order_id).lines == snapshot
    assert reopened.list_lines()[0].revision == 2


def test_duplicate_update_creates_one_order(repo):
    apply(repo, 1, "add", description="pienso", quantity=1)
    first = apply(repo, 2, "buy")
    repo.ingest_batch([message(2)], 3)
    second = repo.apply_intent(2, intent("buy"), "dry_run")
    assert first.order_id is not None
    assert second == first
    assert not repo.pending_messages()
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM orders").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM outbox WHERE update_id=2").fetchone()[0] == 1


def test_apply_and_notice_are_atomic(repo):
    repo.ingest_batch([message()], 2)
    with sqlite3.connect(repo.path) as db:
        db.executescript("""CREATE TRIGGER reject_notice BEFORE INSERT ON outbox
        BEGIN SELECT RAISE(ABORT, 'injected'); END;""")
    with pytest.raises(sqlite3.IntegrityError):
        repo.apply_intent(1, intent("add", description="arroz", quantity=2), "dry_run")
    assert repo.list_lines() == []
    assert repo.pending_messages() == [message()]


def test_restrictions_reject_near_matches():
    rules = {r.id: r for r in PRODUCT_RULES}
    assert validate_product(rules["dog-food"], offer(gtin="0000000000000"))
    assert validate_product(rules["diapers"], offer(brand="Dodot", size=4))
    verified_formula = rules["formula"].model_copy(update={"verified": True})
    assert validate_product(verified_formula, offer(brand="Blemil", variant="Evolution", stage=2)) == [
        "Identidad incompatible: stage"
    ]
    assert not validate_product(
        verified_formula, offer(brand="Blemil", variant="Evolution", stage=1)
    )
    assert not validate_product(rules["dog-food"], offer())
    assert not validate_product(rules["dog-food"], offer(variant="Wild Fish"))
    assert not validate_product(rules["diapers"], offer(brand="Dodot", size=3))
    assert validate_product(rules["formula"], offer(brand="Blemil", variant="Evolution", stage=1))
    assert rules["formula"].gtin is None and rules["formula"].grams is None


@pytest.mark.parametrize("quantity", [0, -1, True, "2"])
def test_quantity_is_strict_and_positive(quantity):
    with pytest.raises(ValidationError):
        IntentLine(quantity=quantity)


def test_unknown_quantity_is_not_invented(repo):
    apply(repo, 1, "add", description="arroz")
    assert repo.list_lines()[0].quantity is None
    reply = apply(repo, 2, "buy")
    assert reply.order_id is None


def test_remove_and_empty_buy(repo):
    apply(repo, 1, "add", description="arroz", quantity=1)
    apply(repo, 2, "remove", line_id=repo.list_lines()[0].id)
    assert repo.list_lines() == []
    assert apply(repo, 3, "buy").order_id is None


def test_config_is_private_and_dry_by_default():
    settings = Settings(telegram_token="secret", authorized_user_id=7, address="PRIVATE_ADDRESS")
    assert settings.mode == "dry_run"
    assert settings.postcode == "28023"
    assert "secret" not in repr(settings) and "PRIVATE_ADDRESS" not in repr(settings)


def test_offer_requires_utc_and_strict_money():
    with pytest.raises(ValidationError):
        offer(price_cents=1.5)
    with pytest.raises(ValidationError):
        offer(observed_at=offer().observed_at.replace(tzinfo=None))


def test_order_snapshot_is_immutable_in_database(repo):
    apply(repo, 1, "add", description="arroz", quantity=1)
    reply = apply(repo, 2, "buy")
    with sqlite3.connect(repo.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE orders SET mode='live' WHERE id=?", (reply.order_id,))
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM order_lines WHERE order_id=?", (reply.order_id,))


@pytest.mark.parametrize("quantities", [(5, 2), (2, 5), (5, None)])
def test_buy_rejects_duplicate_selections_without_mutating_list(repo, quantities):
    apply(repo, 1, "add", description="arroz", quantity=2)
    snapshot = repo.list_lines()
    repo.ingest_batch([message(2)], 3)
    selection = Intent(
        action="buy",
        lines=[IntentLine(line_id=snapshot[0].id, quantity=q) for q in quantities],
    )
    reply = repo.apply_intent(2, selection, "dry_run")
    assert reply.order_id is None
    assert "una sola vez" in reply.text
    assert repo.list_lines() == snapshot
    with sqlite3.connect(repo.path) as db:
        assert db.execute("SELECT count(*) FROM orders").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM order_lines").fetchone()[0] == 0


@pytest.mark.parametrize(
    "description", ["pienso de pollo", "Blemil etapa dos", "pañales de otra marca"]
)
def test_product_resolution_preserves_conflicting_qualifiers(repo, description):
    apply(repo, 1, "add", description=description)
    reopened = Repository(repo.path)
    line = reopened.list_lines()[0]
    assert line.description == description
    assert line.product_id is None
    assert line.quantity is None
