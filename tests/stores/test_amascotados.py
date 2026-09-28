import asyncio

import pytest

from stores.amascotados import Amascotados


@pytest.mark.parametrize('url', [
    'https://www.amascotados.com/carrito?delete=1',
    Amascotados.product_urls[0] + '?delete=1',
    'https://evil.example/alpha-spirit/2883-product.html',
])
def test_read_only_product_rejects_mutating_or_foreign_urls(url):
    with pytest.raises(ValueError):
        asyncio.run(Amascotados().read_product(url, 'dog-food'))


def test_existing_foreign_cart_requires_intervention():
    # Real public probe auto-added a Moments snack. No permission to accept that gift.
    with pytest.raises(RuntimeError, match='intervention'):
        asyncio.run(Amascotados().prepare(None))
