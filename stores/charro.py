import re

from stores.public import PublicStore, price_conditions, product_data


class Charro(PublicStore):
    store_id = 'charro'
    host = 'www.charrodesdecasa.com'
    product_id = 'formula'
    product_urls = (('https://www.charrodesdecasa.com/leches/'
                     '20209-blemil-optimum-evolution-1-800-gr-8426594127534.html'),)

    async def extract(self, page, product_id, url):
        data = await product_data(page)
        title = data['name']
        match = re.fullmatch(r'Blemil Optimum Evolution (\d+) (\d+) gr', title, re.IGNORECASE)
        if not match or data.get('pack') != 0 or data.get('customization_required'):
            raise ValueError('Unsupported formula identity')
        if 'quantity' not in data or data.get('available_for_order') != '1':
            raise ValueError('Unknown availability')
        return self.offer(product_id, url, title, data['price'], data['quantity'] > 0,
                          brand='Blemil', variant='Evolution', stage=int(match[1]),
                          grams=int(match[2]), units_per_pack=1, conditions=price_conditions(data))
