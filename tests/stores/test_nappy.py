import asyncio
import json

from stores.nappy import Nappy
from tests.stores.test_public_adapters import with_page


def test_promotional_quantity_requirement_is_not_silently_eligible():
    async def check(page):
        node = page.locator('#product-details')
        data = json.loads(await node.get_attribute('data-product'))
        data['specific_prices']['from_quantity'] = 3  # Synthetic mutation of real public data.
        await node.evaluate('(e,v)=>e.setAttribute("data-product",v)', json.dumps(data))
        offer = await Nappy().extract(page, 'diapers', Nappy.product_urls[0])
        assert offer.conditions
    asyncio.run(with_page('nappy', check))
