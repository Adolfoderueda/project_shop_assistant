"""Read-only public observations. No checkout or negative-submission evidence."""

import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlsplit

from domain import Capabilities, Offer, Quote, QuotedLine, Reconciliation, Submission
from stores.browser import URLPolicy
from stores.registry import StoreRegistration


def cents(value) -> int:
    amount = Decimal(str(value).replace('\xa0', '').replace('€', '').strip().replace(',', '.'))
    if not amount.is_finite() or amount < 0 or amount * 100 != (amount * 100).to_integral_value():
        raise ValueError('Invalid public price')
    return int(amount * 100)


async def product_data(page) -> dict:
    node = page.locator('#product-details[data-product]')
    if await node.count() != 1:
        raise ValueError('Product evidence missing; intervention required')
    return json.loads(await node.get_attribute('data-product'))


def diaper_identity(title: str, units_text: str | None = None) -> dict:
    if ('dodot' not in title.lower() or '+' in title or
            re.search(r'toallitas|crema|norit|weleda', title, re.IGNORECASE)):
        raise ValueError('Not a diaper-only Dodot pack')
    size = re.search(r'\btalla\s*(\d+)\b', title, re.IGNORECASE)
    units = re.search(r'\b(\d+)\s*(?:uds\.?|unidades)\b', units_text or title, re.IGNORECASE)
    if not size or not units:
        raise ValueError('Missing diaper size/pack evidence')
    return {'brand': 'Dodot', 'size': int(size[1]), 'units_per_pack': int(units[1])}


def price_conditions(data):
    specific = data.get('specific_prices')
    if (data.get('quantity_discounts') or isinstance(specific, dict) and
            (specific.get('from_quantity', 1) != 1 or
             any(specific.get(key, 0) != 0 for key in ('id_customer', 'id_group', 'id_cart')))):
        return ['Conditional price requires basket verification']
    return []


class PublicStore:
    """Bind context to a BrowserManager-managed dedicated profile before reading.

    product_urls/listing_urls are trusted local configuration, not prices or identity.
    An incomplete Quote is intentional: unknown shipping is never zero shipping.
    """

    resource_hosts = frozenset()
    listing_urls = ()
    product_path = r'/[^/]+/\d+-[^/?]+\.html'

    def __init__(self, context=None, *, product_urls=None, listing_urls=None):
        self.context = context
        if product_urls is not None:
            self.product_urls = tuple(product_urls)
        if listing_urls is not None:
            self.listing_urls = tuple(listing_urls)

    def registration(self):
        return StoreRegistration(self.store_id, self, frozenset([self.host]), self.resource_hosts)

    def capabilities(self):
        return Capabilities(search=True, quote=True, prepare=False, submit=False,
                            reconcile=False, live_verified=False)

    async def navigate(self, page, url):
        await URLPolicy(self.registration()).validate(url)
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        if response is None or response.status != 200:
            raise ValueError('Public page unavailable; intervention required')

    def offer(self, product_id, url, title, price, in_stock, *, conditions=None, **identity):
        return Offer(store_id=self.store_id, product_id=product_id, url=url, title=title,
                     price_cents=cents(price), in_stock=in_stock, conditions=conditions or [],
                     observed_at=datetime.now(UTC), **identity)

    async def read_product(self, url, product_id):
        parsed = urlsplit(url)
        if (parsed.hostname != self.host or parsed.query or parsed.fragment or
                not re.fullmatch(self.product_path, parsed.path) or product_id != self.product_id):
            raise ValueError('Not an inspected read-only product URL')
        await URLPolicy(self.registration()).validate(url)
        if self.context is None:
            raise RuntimeError('Bind a dedicated BrowserManager context first')
        page = await self.context.new_page()
        try:
            await self.navigate(page, url)
            return await self.extract(page, product_id, url)
        finally:
            await page.close()

    async def discover(self, rule):
        """Only inspected public product links; search coverage is not exhaustive."""
        urls = list(self.product_urls)
        if self.listing_urls:
            page = await self.context.new_page()
            try:
                for listing in self.listing_urls:
                    await self.navigate(page, listing)
                    links = await page.locator('a[href]').evaluate_all(
                        '(es)=>es.map(e=>({url:e.href,text:e.textContent}))')
                    urls.extend(link['url'] for link in links
                                if '.html' in link['url'] and rule.brand.lower() in link['text'].lower())
            finally:
                await page.close()
        return list(dict.fromkeys(urls))

    async def search(self, rule):
        if rule.id != self.product_id:
            return []
        offers = []
        for url in await self.discover(rule):
            # Unknown/changed pages fail the search, rather than silently claiming coverage.
            try:
                offers.append(await self.read_product(url, rule.id))
            except ValueError:
                # Listings include incompatible ranges and mixed-product bundles.
                # Configured exact references must not silently disappear.
                if url in self.product_urls:
                    raise
        return offers

    async def quote(self, items, destination):
        if not items or any(i.offer.store_id != self.store_id for i in items):
            raise ValueError('Wrong or empty store basket')
        fresh = [QuotedLine(line_id=i.line_id, packs=i.packs,
                            offer=await self.read_product(i.offer.url, i.offer.product_id))
                 for i in items]
        return Quote(store_id=self.store_id, items=fresh, observed_at=datetime.now(UTC))

    async def prepare(self, quote):
        raise RuntimeError('Checkout identity/destination/cart unverified; intervention required')

    async def submit(self, cart, attempt_id):
        return Submission(status='requires_intervention',
                          reason='Checkout/payment not inspected with a user session; no action taken')

    async def reconcile(self, attempt_id, cart):
        return Reconciliation(status='unknown')
