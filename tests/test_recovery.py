import pytest

from checkout import CheckoutService
from recovery import Recovery
from storage import Repository
from tests.fakes import FakeStore, async_test
from tests.test_checkout import DESTINATION, apply, offer, order


@pytest.fixture
def repo(tmp_path):
    result = Repository(tmp_path / "recovery.sqlite")
    result.migrate()
    return result


@async_test
async def test_lost_response_reconciles_without_resubmit(repo):
    oid = order(repo)
    store = FakeStore("a", [offer()])
    store.lose_response = True
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert repo.order_status(oid) == "resultado_incierto"
    assert repo.list_lines()
    reopened = Repository(repo.path)
    await Recovery(reopened, {"a": store}).recover()
    assert store.submit_calls == 1
    assert reopened.order_status(oid) == "confirmado"
    assert not reopened.list_lines()
    await Recovery(reopened, {"a": store}).recover()
    assert store.submit_calls == 1


@async_test
async def test_unknown_and_resume_never_blind_retry(repo):
    oid = order(repo)
    store = FakeStore("a", [offer()])
    store.intervention = True
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    reply = apply(repo, "resume", order_id=oid)
    assert reply.order_id == oid
    await Recovery(repo, {"a": store}).recover()
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert store.submit_calls == 1
    assert repo.list_lines()


@async_test
async def test_confirmation_transaction_failure_recovers_once(repo):
    oid = order(repo)
    store = FakeStore("a", [offer()])
    with repo._connection(write=True) as db:
        db.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON list_lines "
                   "BEGIN SELECT RAISE(ABORT, 'injected'); END")
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert repo.list_lines()
    assert repo.uncertain_attempts()
    with repo._connection(write=True) as db:
        db.execute("DROP TRIGGER fail_delete")
    await Recovery(Repository(repo.path), {"a": store}).recover()
    assert store.submit_calls == 1
    assert not repo.list_lines()


@async_test
async def test_split_line_confirmed_only_after_remaining_allocation(repo):
    from catalog import PRODUCT_RULES
    from domain import Submission
    from offers import PurchaseRequest
    oid = order(repo, description="dodot", quantity=100)
    line = repo.get_order(oid).lines[0]
    repo.set_purchase_requests(oid, [PurchaseRequest(line_id=line.id, rule=PRODUCT_RULES[1],
                                                   quantity=100, quantity_unit="pieces")])
    a, b = FakeStore("a", [offer("a", "diapers", 40)]), FakeStore("b", [offer("b", "diapers", 60)])
    b.intervention = True
    await CheckoutService(repo, {"a": a, "b": b}, DESTINATION).run(oid)
    attempt, cart = repo.uncertain_attempts()[0]
    b.ledger[attempt] = Submission(status="confirmed", external_id="bank-confirmed",
                                   total_cents=cart.quote.total_cents, delivery="tomorrow")
    await Recovery(Repository(repo.path), {"a": a, "b": b}).recover()
    assert not repo.list_lines()
    assert a.submit_calls == b.submit_calls == 1
    assert repo.order_status(oid) == "confirmado"


@async_test
async def test_definitely_not_submitted_requires_resume_and_only_retries_remaining(repo):
    from domain import Reconciliation
    oid = order(repo)
    store = FakeStore("a", [offer()])
    store.intervention = True
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    async def negative(attempt_id, cart):
        return Reconciliation(status="definitely_not_submitted")
    store.reconcile = negative
    await Recovery(repo, {"a": store}).recover()
    assert not repo.pending_orders()
    apply(repo, "resume", order_id=oid)
    await Recovery(repo, {"a": store}).recover()
    store.intervention = False
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert store.submit_calls == 2
    assert not repo.list_lines()


@async_test
async def test_no_external_evidence_is_not_confirmation(repo):
    from domain import Submission
    oid = order(repo)
    store = FakeStore("a", [offer()])
    async def unsupported(cart, attempt_id):
        return Submission(status="confirmed")
    store.submit = unsupported
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert repo.order_status(oid) == "resultado_incierto"
    assert repo.list_lines()


@async_test
async def test_process_death_after_durable_attempt_does_not_resubmit(repo):
    oid = order(repo)
    store = FakeStore("a", [offer()])
    def die(attempt_id):
        raise SystemExit("simulated process death")
    store.before_submit = die
    with pytest.raises(SystemExit):
        await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    assert repo.order_status(oid) == "enviando"
    await Recovery(Repository(repo.path), {"a": store}).recover()
    assert repo.order_status(oid) == "resultado_incierto"
    assert store.submit_calls == 1


@async_test
async def test_repeated_unknown_reconciliation_does_not_flood_outbox(repo):
    oid = order(repo)
    store = FakeStore("a", [offer()])
    store.intervention = True
    await CheckoutService(repo, {"a": store}, DESTINATION).run(oid)
    await Recovery(repo, {"a": store}).recover()
    count = len(repo.pending_notices())
    await Recovery(repo, {"a": store}).recover()
    assert len(repo.pending_notices()) == count


@async_test
@pytest.mark.parametrize("negative_first", [True, False])
async def test_sibling_confirmation_cannot_unlock_negative_without_resume(repo, negative_first):
    from catalog import PRODUCT_RULES
    from domain import Reconciliation, Submission
    from offers import PurchaseRequest

    oid = order(repo, description="dodot", quantity=100)
    line = repo.get_order(oid).lines[0]
    repo.set_purchase_requests(oid, [PurchaseRequest(line_id=line.id, rule=PRODUCT_RULES[1],
                                                   quantity=100, quantity_unit="pieces")])
    a, b = FakeStore("a", [offer("a", "diapers", 40)]), FakeStore("b", [offer("b", "diapers", 60)])
    a.intervention = b.intervention = True
    await CheckoutService(repo, {"a": a, "b": b}, DESTINATION).run(oid)
    attempts = repo.uncertain_attempts()
    negative_id, negative_cart = attempts[0 if negative_first else 1]
    confirmed_id, confirmed_cart = attempts[1 if negative_first else 0]
    stores = {"a": a, "b": b}
    negative_store = stores[negative_cart.quote.store_id]
    confirmed_store = stores[confirmed_cart.quote.store_id]

    async def negative(attempt_id, cart):
        assert attempt_id == negative_id
        return Reconciliation(status="definitely_not_submitted")
    negative_store.reconcile = negative
    confirmed_store.ledger[confirmed_id] = Submission(
        status="confirmed", external_id="external-confirmed", total_cents=confirmed_cart.quote.total_cents,
        delivery="tomorrow")
    await Recovery(Repository(repo.path), stores).recover()
    assert repo.pending_orders() == []
    assert repo.order_status(oid) == "requiere_intervencion"
    await CheckoutService(repo, stores, DESTINATION).run(oid)
    assert a.submit_calls == b.submit_calls == 1
    assert repo.list_lines()
    apply(repo, "resume", order_id=oid)
    await Recovery(repo, stores).recover()
    assert repo.pending_orders() == [oid]
    negative_store.intervention = False
    await CheckoutService(repo, stores, DESTINATION).run(oid)
    assert negative_store.submit_calls == 2
    assert confirmed_store.submit_calls == 1
    assert repo.order_status(oid) == "confirmado"
    assert not repo.list_lines()
