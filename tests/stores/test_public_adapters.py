import asyncio
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from catalog import PRODUCT_RULES
from domain import Destination, QuotedLine

CASES = [
    ('amascotados', 'Amascotados', 0, 6399, 1, 12000),
    ('charro', 'Charro', 2, 2515, 1, 800),
    ('nappy', 'Nappy', 1, 4687, 186, None),
    ('mercadona', 'Mercadona', 1, 1695, 56, None),
]


def adapter(name, cls):
    import importlib
    module = importlib.import_module('stores.' + name)
    return getattr(module, cls)(None)


async def with_page(name, fn):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page()
            await page.route('**/*', lambda r: r.abort())
            await page.set_content(Path(f'tests/fixtures/stores/{name}.html').read_text('utf8'))
            return await fn(page)
        finally:
            await browser.close()


@pytest.mark.parametrize('name,cls,index,cents,units,grams', CASES)
def test_exact_product_extraction(name, cls, index, cents, units, grams):
    store = adapter(name, cls)
    async def check(page):
        offer = await store.extract(page, PRODUCT_RULES[index].id, store.product_urls[0])
        assert (offer.price_cents, offer.units_per_pack, offer.grams) == (cents, units, grams)
        assert offer.brand == PRODUCT_RULES[index].brand
        assert offer.in_stock
        # No independent GTIN field in these public captures. Never parse URL as evidence.
        assert offer.gtin is None
        if index == 1:
            assert offer.size == 3
        if index == 2:
            assert offer.stage == 1 and offer.variant == 'Evolution'
    asyncio.run(with_page(name, check))


def test_out_of_stock_real_nappy_capture():
    store = adapter('nappy', 'Nappy')
    async def check(page):
        offer = await store.extract(page, 'diapers', store.product_urls[0])
        assert not offer.in_stock
        assert offer.price_cents == 3125 and offer.units_per_pack == 56
    asyncio.run(with_page('nappy-out', check))


@pytest.mark.parametrize('name,cls,index,cents,units,grams', CASES)
def test_unknown_stock_and_changed_identity_fail_closed(name, cls, index, cents, units, grams):
    store = adapter(name, cls)
    async def check(page):
        # Synthetic deletion, not represented as a live out-of-stock capture.
        await page.set_content('<h1>unavailable / CAPTCHA / login</h1>')
        with pytest.raises(ValueError):
            await store.extract(page, PRODUCT_RULES[index].id, store.product_urls[0])
    asyncio.run(with_page(name, check))


@pytest.mark.parametrize('name,cls,index,cents,units,grams', CASES)
def test_uninspected_checkout_never_mutates_or_asserts_negative(name, cls, index, cents, units, grams):
    store = adapter(name, cls)  # No browser: any accidental remote operation fails.
    async def check():
        with pytest.raises(RuntimeError, match='intervention'):
            await store.prepare(None)
        result = await store.submit(None, 'unknown-attempt')
        assert result.status == 'requires_intervention'
        assert result.external_id is None
        assert (await store.reconcile('unknown-attempt', None)).status == 'unknown'
    asyncio.run(check())
    caps = store.capabilities()
    assert caps.search and caps.quote
    assert not any((caps.prepare, caps.submit, caps.reconcile, caps.live_verified))


def test_quote_refreshes_product_without_inventing_shipping():
    store = adapter('nappy', 'Nappy')
    async def check(page):
        old = await store.extract(page, 'diapers', store.product_urls[0])
        stale = old.model_copy(update={'price_cents': 1})
        async def read(url, product_id):
            return await store.extract(page, product_id, url)
        store.read_product = read
        quote = await store.quote([QuotedLine(line_id='line', offer=stale, packs=2)],
                                  Destination(postcode='28023', address='Private test address'))
        assert quote.items[0].offer.price_cents == 4687
        assert quote.items[0].packs == 2
        assert quote.shipping_cents is None and quote.total_cents is None
        assert quote.delivery is None
    asyncio.run(with_page('nappy', check))


def test_quote_rejects_changed_pack_identity():
    store = adapter('mercadona', 'Mercadona')

    async def check(page):
        old = await store.extract(page, 'diapers', store.product_urls[0])
        changed_pack = old.model_copy(update={'units_per_pack': 40, 'price_cents': 1295})

        async def read(url, product_id):
            return changed_pack

        store.read_product = read
        with pytest.raises(ValueError, match='identity'):
            await store.quote([QuotedLine(line_id='line', offer=old, packs=1)],
                              Destination(postcode='28023', address='Synthetic address'))

    asyncio.run(with_page('mercadona', check))


def test_explicit_registry_and_host_policy():
    from stores.connections import registrations
    entries = registrations()
    assert {e.store_id for e in entries} == {c[0] for c in CASES}
    merc = next(e for e in entries if e.store_id == 'mercadona')
    assert 'tornillos.mercadona.es' in merc.resource_hosts
    assert 'tornillos.mercadona.es' not in merc.navigation_hosts

