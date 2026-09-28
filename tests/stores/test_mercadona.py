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
