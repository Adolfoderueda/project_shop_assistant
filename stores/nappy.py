from stores.public import PublicStore, diaper_identity, price_conditions, product_data


class Nappy(PublicStore):
    store_id = 'nappy'
    host = 'nappy.es'
    product_id = 'diapers'
    product_urls = ('https://nappy.es/dodot/6035-panales-talla-3-bebe-seco-dodot.html',)
    listing_urls = ('https://nappy.es/1087-talla-3',)

    async def extract(self, page, product_id, url):
        data = await product_data(page)
        identity = diaper_identity(data['name'])
        if data.get('availability') not in ('in_stock', 'unavailable'):
            raise ValueError('Unknown availability')
        if data.get('customization_required'):
            raise ValueError('Pack requires selection')
        quantity = data.get('quantity')
        in_stock = (data['availability'] == 'in_stock' and
                    data.get('available_for_order') == '1' and
                    type(quantity) is int and quantity > 0)
        return self.offer(product_id, url, data['name'], data['price_amount'],
                          in_stock, conditions=price_conditions(data), **identity)
