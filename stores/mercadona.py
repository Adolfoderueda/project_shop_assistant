import re
from urllib.parse import urlencode

from stores.public import PublicStore, diaper_identity


class Mercadona(PublicStore):
    store_id = 'mercadona'
    host = 'tienda.mercadona.es'
    product_id = 'diapers'
    product_path = r'/product/\d+/[a-z0-9-]+'
    resource_hosts = frozenset(['farolas.mercadona.es', 'featureflags.mercadona.es',
                                'prod-mercadona.imgix.net', 'tornillos.mercadona.es'])
    product_urls = (('https://tienda.mercadona.es/product/52879/'
                     'panales-bebe-talla-3-6-10-kg-dodot-sensitive-paquete'),)

    async def open_catalogue(self, page):
        await super().navigate(page, 'https://tienda.mercadona.es/')
        await page.locator('input[name="search"]').wait_for()
        reject = page.get_by_role('button', name='Rechazar', exact=True)
        if await reject.count():
            await reject.click()
        postcode = page.locator('input[name="postalCode"]')
        if await postcode.count():
            await postcode.fill('28023')
            await postcode.press('Enter')
            await postcode.wait_for(state='detached')
        await self.verify_region(page)

    async def navigate(self, page, url):
        await self.open_catalogue(page)
        await super().navigate(page, url)
        await page.locator('.private-product-detail__right').wait_for(timeout=20000)

    async def search_names(self, page, rule):
        names = await page.locator('.product-cell__description-name').all_text_contents()
        return list(dict.fromkeys(name for name in names if rule.brand.lower() in name.lower()
                                   and re.search(rf'\btalla\s+{rule.size}\b', name, re.IGNORECASE)))

    async def discover(self, rule):
        page = await self.context.new_page()
        try:
            await self.open_catalogue(page)
            search_url = 'https://tienda.mercadona.es/search-results?' + urlencode({'query': rule.brand})
            await super().navigate(page, search_url)
            await page.locator('.product-cell__content-link').first.wait_for(timeout=20000)
            names = await self.search_names(page, rule)
            urls = list(self.product_urls)
            for name in names:
                await page.locator('.product-cell__content-link').filter(has_text=name).click()
                await page.locator('.private-product-detail__right').wait_for(timeout=20000)
                urls.append(page.url)
                await super().navigate(page, search_url)
                await page.locator('.product-cell__content-link').first.wait_for(timeout=20000)
            return list(dict.fromkeys(urls))
        finally:
            await page.close()

    async def verify_region(self, page):
        region = page.locator('.select-delivery-area')
        if (await region.count() != 1 or
                await region.get_attribute('aria-label') != 'Entregar en código postal 28023'):
            raise ValueError('Public catalogue region is not verified as 28023; intervention required')

    async def extract(self, page, product_id, url):
        root = page.locator('.private-product-detail__right')
        if await root.count() != 1:
            raise ValueError('Missing public product detail')
        title = await root.locator('h1').text_content()
        identity = diaper_identity(title, await root.locator('.product-format .sr-only').text_content())
        button = root.locator('.product-quantity-button__add')
        in_stock = await button.count() == 1 and await button.is_enabled()
        return self.offer(product_id, url, title,
                          await root.locator('.product-price__unit-price').text_content(),
                          in_stock, **identity)
