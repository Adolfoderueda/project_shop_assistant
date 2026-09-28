from datetime import UTC, datetime

import pytest

from checkout import CheckoutService
from domain import Destination, IncomingMessage, Intent, IntentLine, Offer
from storage import Repository
from tests.fakes import FakeStore, async_test

DESTINATION = Destination(postcode="28023", address="private test address")


def apply(repo, action, lines=(), mode="live", order_id=None):
    update = repo.telegram_offset()
    repo.ingest_batch([IncomingMessage(update_id=update, user_id=1, chat_id=2, text=action)],
                      update + 1)
    return repo.apply_intent(update, Intent(action=action, lines=list(lines), order_id=order_id), mode)


def offer(store="a", product="dog-food", units=1, price=100):
    return Offer(store_id=store, product_id=product, url=f"https://{store}.example/{units}",
                 title="test", brand="Alpha Spirit" if product == "dog-food" else "Dodot",
                 variant="Only Fish" if product == "dog-food" else None,
                 grams=12000 if product == "dog-food" else None,
                 gtin="8436586310295" if product == "dog-food" else None,
                 size=3 if product == "diapers" else None, units_per_pack=units,
                 price_cents=price, in_stock=True, conditions=[], observed_at=datetime.now(UTC))


@pytest.fixture
def repo(tmp_path):
    repo = Repository(tmp_path / "state.sqlite")
    repo.migrate()
    return repo


def order(repo, mode="live", description="pienso", quantity=2):
    apply(repo, "add", [IntentLine(description=description, quantity=quantity)])
    return apply(repo, "buy", mode=mode).order_id


@async_test
async def test_dry_run_never_calls_submit(repo):
    oid = order(repo, mode="dry_run")
    store = FakeStore("a", [offer()])
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert store.submit_calls == store.prepare_calls == 0
    assert repo.order_status(oid) == "simulado"
    assert len(repo.list_lines()) == 1
    assert any("simulado" in text for _, _, text in repo.pending_notices())


@async_test
async def test_edit_during_checkout_preserves_new_revision(repo):
    oid = order(repo)
    line = repo.list_lines()[0]
    store = FakeStore("a", [offer()])
    def edit(attempt_id):
        assert repo.uncertain_attempts()[0][0] == attempt_id
        apply(repo, "set_quantity", [IntentLine(line_id=line.id, quantity=5)])
    store.before_submit = edit
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert repo.list_lines()[0].quantity == 5
    assert repo.list_lines()[0].revision == 2
    assert repo.order_status(oid) == "confirmado"


def test_second_purchase_does_not_claim_already_pending_lines(repo):
    oid = order(repo)
    assert oid
    assert apply(repo, "buy").order_id is None
    assert repo.pending_orders() == [oid]
    assert repo.claim_order(oid)
    assert not Repository(repo.path).claim_order(oid)


@async_test
async def test_cart_fingerprint_change_requotes(repo):
    oid = order(repo)
    store = FakeStore("a", [offer()])
    store.change_cart = True
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert store.submit_calls == 0
    assert store.quote_calls >= 2
    assert repo.order_status(oid) == "requiere_intervencion"
    assert any("cambi" in text.lower() for _, _, text in repo.pending_notices())


@async_test
async def test_partial_success_preserves_remaining_lines(repo):
    from catalog import PRODUCT_RULES
    from offers import PurchaseRequest
    oid = order(repo, description="dodot", quantity=100)
    line = repo.get_order(oid).lines[0]
    repo.set_purchase_requests(oid, [PurchaseRequest(line_id=line.id, rule=PRODUCT_RULES[1],
                                                   quantity=100, quantity_unit="pieces")])
    a = FakeStore("a", [offer("a", "diapers", 40)])
    b = FakeStore("b", [offer("b", "diapers", 60)])
    b.intervention = True
    service = CheckoutService(repo, {"a": a, "b": b}, DESTINATION)
    await service.run(oid)
    assert a.submit_calls == b.submit_calls == 1
    assert repo.list_lines()[0].quantity == 100
    assert apply(repo, "buy").order_id is None
    await service.run(oid)
    assert a.submit_calls == b.submit_calls == 1
    assert repo.order_status(oid) == "requiere_intervencion"


@async_test
async def test_status_after_partial_success_restart_lists_store_evidence_and_unresolved(repo):
    from catalog import PRODUCT_RULES
    from offers import PurchaseRequest

    oid = order(repo, description="dodot", quantity=100)
    line = repo.get_order(oid).lines[0]
    repo.set_purchase_requests(oid, [PurchaseRequest(line_id=line.id, rule=PRODUCT_RULES[1],
                                                      quantity=100, quantity_unit="pieces")])
    a = FakeStore("a", [offer("a", "diapers", 40)])
    b = FakeStore("b", [offer("b", "diapers", 60)])
    b.intervention = True
    await CheckoutService(repo, {"a": a, "b": b}, DESTINATION).run(oid)
    reopened = Repository(repo.path)
    reopened.migrate()
    status = apply(reopened, "status", order_id=oid).text
    assert "requiere_intervencion" in status
    assert "a: confirmado" in status
    assert "b: requiere_intervencion" in status
    confirmed = next(s for s in reopened.suborders(oid) if s["store_id"] == "a")
    assert confirmed["external_id"] in status
    assert str(confirmed["total_cents"]) in status
    assert line.id in status and "sin resolver" in status
    assert DESTINATION.address not in status


@async_test
async def test_unverified_product_does_not_block_unrelated_list_operations(repo):
    apply(repo, "add", [IntentLine(description="formula", quantity=1)])
    oid = order(repo)
    store = FakeStore("a", [offer()])
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert store.submit_calls == 0
    assert repo.order_status(oid) == "requiere_intervencion"
    assert "formula" in apply(repo, "list").text
    dog = next(l for l in repo.list_lines() if l.product_id == "dog-food")
    assert apply(repo, "set_quantity", [IntentLine(line_id=dog.id, quantity=3)])


@async_test
async def test_sqlite_attempt_failure_prevents_submit(repo):
    oid = order(repo)
    with repo._connection(write=True) as db:
        db.execute("CREATE TRIGGER fail_attempt BEFORE INSERT ON attempts "
                   "BEGIN SELECT RAISE(ABORT, 'injected'); END")
    store = FakeStore("a", [offer()])
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert store.submit_calls == 0
    assert repo.uncertain_attempts() == []
    assert repo.list_lines()


@async_test
async def test_price_refresh_is_not_a_new_financial_approval(repo):
    oid = order(repo)
    store = FakeStore("a", [offer()])
    original = store.quote
    async def changing_quote(items, destination):
        result = await original(items, destination)
        if store.quote_calls > 1:
            return result.model_copy(update={"shipping_cents": 50,
                                             "total_cents": result.total_cents + 50})
        return result
    store.quote = changing_quote
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert store.submit_calls == 1
    assert repo.order_status(oid) == "confirmado"
    assert repo.suborders(oid)[0]["total_cents"] == 250
    assert any("precio" in text.lower() for _, _, text in repo.pending_notices())


@async_test
@pytest.mark.parametrize("corruption", ["destination", "identity", "quantity", "foreign", "delivery", "fingerprint"])
async def test_unverifiable_prepared_cart_never_submits(repo, corruption):
    from domain import QuotedLine
    from offers import cart_fingerprint
    oid = order(repo)
    store = FakeStore("a", [offer()])
    original = store.prepare
    async def corrupt(quote):
        cart = await original(quote)
        if corruption == "destination":
            return cart.model_copy(update={"destination": None})
        if corruption == "fingerprint":
            return cart.model_copy(update={"fingerprint": "forged"})
        if corruption == "delivery":
            quote = quote.model_copy(update={"delivery": None})
        else:
            item = quote.items[0]
            if corruption == "identity":
                item = item.model_copy(update={"offer": item.offer.model_copy(update={"brand": "other"})})
            if corruption == "quantity":
                item = item.model_copy(update={"packs": 3})
            if corruption == "foreign":
                item = QuotedLine(line_id="other", offer=item.offer, packs=item.packs)
            quote = quote.model_copy(update={"items": [item], "total_cents": item.packs * item.offer.price_cents})
        return cart.model_copy(update={"quote": quote, "fingerprint": cart_fingerprint(quote)})
    store.prepare = corrupt
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert store.submit_calls == 0
    assert repo.list_lines()


def test_prepared_order_is_selectable_after_restart(repo):
    from domain import Quote, QuotedLine
    oid = order(repo)
    line = repo.get_order(oid).lines[0]
    quote = Quote(store_id="a", items=[QuotedLine(line_id=line.id, offer=offer(), packs=2)],
                  total_cents=200, shipping_cents=0, delivery="tomorrow", observed_at=datetime.now(UTC))
    repo.save_assignment(oid, [quote])
    assert Repository(repo.path).pending_orders() == [oid]


@async_test
async def test_confirmed_snapshot_can_be_bought_again_only_after_edit(repo):
    oid = order(repo)
    store = FakeStore("a", [offer()])
    line = repo.list_lines()[0]
    store.before_submit = lambda _: apply(repo, "set_quantity", [IntentLine(line_id=line.id, quantity=3)])
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert apply(repo, "buy").order_id is not None


@async_test
async def test_explicit_requests_cannot_bypass_newly_unverified_catalog(repo):
    from offers import PurchaseRequest
    oid = order(repo)
    line = repo.get_order(oid).lines[0]
    rule = repo.product_rule(line.product_id)
    repo.set_purchase_requests(oid, [PurchaseRequest(line_id=line.id, rule=rule, quantity=2)])
    with repo._connection(write=True) as db:
        db.execute("UPDATE products SET rule_json=? WHERE id=?",
                   (rule.model_copy(update={"verified": False}).model_dump_json(), rule.id))
    store = FakeStore("a", [offer()])
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert store.submit_calls == 0


def test_migration_quarantines_legacy_unreserved_orders(tmp_path):
    import sqlite3
    from pathlib import Path
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as db:
        for migration in ("001.sql", "002.sql"):
            db.executescript((Path("migrations") / migration).read_text())
        db.execute("INSERT INTO inbox(update_id,user_id,chat_id,text) VALUES (1,1,2,'buy')")
        db.execute("INSERT INTO orders(id,mode,source_update_id) VALUES ('legacy','live',1)")
    migrated = Repository(path)
    migrated.migrate()
    assert migrated.pending_orders() == []
    assert migrated.order_status("legacy") == "requiere_intervencion"


@async_test
async def test_repository_rejects_attempt_not_matching_durable_allocation(repo):
    from domain import QuotedLine
    oid = order(repo)
    line = repo.get_order(oid).lines[0]
    store = FakeStore("a", [offer()])
    quote = await store.quote([QuotedLine(line_id=line.id, offer=offer(), packs=2)], DESTINATION)
    repo.save_assignment(oid, [quote])
    other = await store.quote([QuotedLine(line_id=line.id, offer=offer(), packs=3)], DESTINATION)
    cart = await store.prepare(other)
    with pytest.raises(ValueError):
        repo.save_attempt(oid, "a", cart)
    assert not repo.uncertain_attempts()


@async_test
async def test_overlapping_legacy_orders_stay_quarantined_on_resume(tmp_path):
    import sqlite3
    from pathlib import Path

    from catalog import PRODUCT_RULES
    from domain import ListLine
    from offers import PurchaseRequest
    from recovery import Recovery

    path = tmp_path / "overlap.sqlite"
    line = ListLine(id="legacy-line", product_id="dog-food", description="pienso", quantity=2, revision=1)
    with sqlite3.connect(path) as db:
        for migration in ("001.sql", "002.sql"):
            db.executescript((Path("migrations") / migration).read_text())
        db.execute("INSERT INTO products VALUES (?,?)", (PRODUCT_RULES[0].id, PRODUCT_RULES[0].model_dump_json()))
        for update, oid in enumerate(("legacy-a", "legacy-b"), 1):
            db.execute("INSERT INTO inbox(update_id,user_id,chat_id,text) VALUES (?,1,2,'buy')", (update,))
            db.execute("INSERT INTO orders(id,mode,source_update_id) VALUES (?,'live',?)", (oid, update))
            db.execute("INSERT INTO order_lines VALUES (?,0,?)", (oid, line.model_dump_json()))
        db.execute("INSERT INTO list_lines VALUES (?,?,?,?,1,1)", (line.id, line.product_id, line.description, 2))
        db.execute("UPDATE meta SET value=3 WHERE key='telegram_offset'")
    repo = Repository(path)
    repo.migrate()
    store = FakeStore("a", [offer()])
    for oid in ("legacy-a", "legacy-b", "legacy-a"):
        reply = apply(repo, "resume", order_id=oid)
        await Recovery(repo, {"a": store}).recover()
        await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
        assert repo.order_status(oid) == "requiere_intervencion"
        assert "cuarentena" in reply.text.lower()
    assert store.submit_calls == store.prepare_calls == 0
    assert repo.pending_orders() == []
    assert repo.list_lines() == [line]
    assert not repo.uncertain_attempts()
    with pytest.raises(ValueError, match="not executable"):
        repo.set_purchase_requests("legacy-a", [PurchaseRequest(
            line_id=line.id, rule=PRODUCT_RULES[0], quantity=2)])


@async_test
async def test_missing_reservation_blocks_remote_checkout_even_after_resume(repo):
    from recovery import Recovery

    oid = order(repo)
    with repo._connection(write=True) as db:
        db.execute("DELETE FROM reservations WHERE order_id=?", (oid,))
    store = FakeStore("a", [offer()])
    for _ in range(2):
        apply(repo, "resume", order_id=oid)
        await Recovery(repo, {"a": store}).recover()
        await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert store.prepare_calls == store.submit_calls == 0
    assert repo.list_lines()


@async_test
async def test_reassigning_reservation_cannot_rebuy_fulfilled_snapshot(repo):
    oid = order(repo)
    snapshot = repo.get_order(oid).lines[0]
    store = FakeStore("a", [offer()])
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert repo.order_status(oid) == "confirmado"
    update = repo.telegram_offset()
    repo.ingest_batch([IncomingMessage(update_id=update, user_id=1, chat_id=2, text="local review")], update + 1)
    # Simulate a mistaken local conflict resolution: another order now owns the
    # old line reservation. Immutable confirmed snapshots must still block it.
    with repo._connection(write=True) as db:
        db.execute("INSERT INTO orders(id,mode,source_update_id) VALUES ('reassigned','live',?)", (update,))
        db.execute("INSERT INTO order_lines VALUES ('reassigned',0,?)", (snapshot.model_dump_json(),))
        db.execute("INSERT INTO execution(order_id) VALUES ('reassigned')")
        db.execute("INSERT INTO reservations VALUES (?,'reassigned')", (snapshot.id,))
    assert repo.pending_orders() == []
    await CheckoutService(repo, {"a": store}, DESTINATION).run("reassigned")
    assert store.prepare_calls == store.submit_calls == 1
    assert repo.order_status("reassigned") == "requiere_intervencion"


def test_v3_upgrade_preserves_durable_quarantine_across_reopen(tmp_path):
    import sqlite3
    from pathlib import Path

    path = tmp_path / "v3.sqlite"
    with sqlite3.connect(path) as db:
        for migration in ("001.sql", "002.sql", "003.sql"):
            db.executescript((Path("migrations") / migration).read_text())
        db.execute("INSERT INTO inbox(update_id,user_id,chat_id,text) VALUES (1,1,2,'buy')")
        db.execute("INSERT INTO orders(id,mode,source_update_id) VALUES ('v3','live',1)")
        db.execute("INSERT INTO execution(order_id) VALUES ('v3')")
        db.execute("UPDATE meta SET value=2 WHERE key='telegram_offset'")
    repo = Repository(path)
    repo.migrate()
    reopened = Repository(path)
    reopened.migrate()
    assert "cuarentena" in apply(reopened, "resume", order_id="v3").text
    assert reopened.pending_orders() == reopened.resumable_orders() == []
    assert reopened.order_status("v3") == "requiere_intervencion"
