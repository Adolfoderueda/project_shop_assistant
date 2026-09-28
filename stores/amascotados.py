import re

from catalog import DOG_URL
from stores.public import PublicStore


class Amascotados(PublicStore):
    store_id = 'amascotados'
    host = 'www.amascotados.com'
    product_id = 'dog-food'
    product_urls = (DOG_URL,)
    listing_urls = ('https://www.amascotados.com/buscar?controller=search&s=Alpha+Spirit',)

    async def extract(self, page, product_id, url):
        root = page.locator('.cn_product_visited')
        if await root.count() != 1:
            raise ValueError('Missing product evidence')
        title = await root.locator('.name').text_content()
        match = re.fullmatch(r'Alpha Spirit (Wild Fish|Only Fish) (\d+) Kg', title.strip(), re.IGNORECASE)
        if not match:
            raise ValueError('Unsupported food identity')
        stock = (await root.locator('.availability').text_content()).strip()
        if stock not in ('instock', 'outofstock'):
            raise ValueError('Unknown availability')
        return self.offer(product_id, url, title, await root.locator('.unit_price').text_content(),
                          stock == 'instock', brand=(await root.locator('.brand').text_content()).strip(),
                          variant=match[1].title(), grams=int(match[2]) * 1000, units_per_pack=1)
