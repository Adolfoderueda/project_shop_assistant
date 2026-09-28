import asyncio

from stores.charro import Charro


def test_checkout_requires_bank_action():
    # No captured bank/3DS screen; the unimplemented payment gate never acts.
    result = asyncio.run(Charro().submit(None, 'bank-not-inspected'))
    assert result.status == 'requires_intervention'
    assert result.external_id is None


def test_success_requires_order_reference():
    # No authenticated history: even an apparently empty history is not negative evidence.
    result = asyncio.run(Charro().reconcile('no-order-reference', None))
    assert result.status == 'unknown' and result.submission is None
