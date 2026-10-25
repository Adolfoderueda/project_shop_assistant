import asyncio

import pytest

from catalog import PRODUCT_RULES
from stores.mercadona import Mercadona
from tests.stores.test_public_adapters import with_page


def test_existing_wrong_postcode_is_not_assumed_28023():
    async def check(page):
        # Synthetic wrong-region fixture; no real address involved.
        await page.set_content('<button class="select-delivery-area" '
                               'aria-label="Entregar en código postal 28024"></button>')
        with pytest.raises(ValueError, match='28023'):
            await Mercadona().verify_region(page)
    asyncio.run(with_page('mercadona', check))


def test_public_search_discovers_names_without_guessing_product_urls():
    async def check(page):
        names = await Mercadona().search_names(page, PRODUCT_RULES[1])
        assert names == ['Pañales bebé talla 3 Dodot Sensitive de 6-10 kg']
    asyncio.run(with_page('mercadona-search', check))


def test_changed_price_is_extracted_from_current_product_detail():
    async def check(page):
        await page.locator('.product-price__unit-price').evaluate(
            '(node) => { node.textContent = "18,45 €"; }')
        offer = await Mercadona().extract(page, 'diapers', Mercadona.product_urls[0])
        assert offer.price_cents == 1845
        assert offer.units_per_pack == 56
    asyncio.run(with_page('mercadona', check))


def test_unavailable_product_does_not_keep_cached_available_state():
    async def check(page):
        await page.locator('.product-quantity-button__add').evaluate('(node) => node.remove()')
        offer = await Mercadona().extract(page, 'diapers', Mercadona.product_urls[0])
        assert not offer.in_stock
    asyncio.run(with_page('mercadona', check))


def test_timeout_does_not_return_cached_price():
    store = Mercadona()

    async def timed_out_read(url, product_id):
        raise TimeoutError('Synthetic public-site timeout')

    store.read_product = timed_out_read

    async def check(page):
        from domain import Destination, QuotedLine

        cached = await store.extract(page, 'diapers', store.product_urls[0])
        with pytest.raises(TimeoutError, match='timeout'):
            await store.quote([QuotedLine(line_id='line', offer=cached, packs=1)],
                              Destination(postcode='28023', address='Synthetic address'))

    asyncio.run(with_page('mercadona', check))


def test_quote_rejects_changed_product_title_with_same_pack_identity():
    async def check(page):
        from domain import Destination, QuotedLine

        store = Mercadona()
        original = await store.extract(page, 'diapers', store.product_urls[0])
        await page.locator('h1').evaluate(
            "(node) => { node.textContent = node.textContent.replace('Sensitive ', ''); }")

        async def read_product(url, product_id):
            return await store.extract(page, product_id, url)

        store.read_product = read_product
        changed = await read_product(store.product_urls[0], 'diapers')
        assert changed.units_per_pack == original.units_per_pack == 56
        assert changed.size == original.size == 3
        assert changed.variant is original.variant is None
        assert changed.title != original.title
        with pytest.raises(ValueError, match='identity'):
            await store.quote(
                [QuotedLine(line_id='line', offer=original, packs=1)],
                Destination(postcode='28023', address='Synthetic address'))

    asyncio.run(with_page('mercadona', check))