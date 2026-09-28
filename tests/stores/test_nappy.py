import asyncio
import json

import pytest

from stores.nappy import Nappy
from stores.public import diaper_identity
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


@pytest.mark.parametrize('title,units', [
    ('Pack Dodot 2 cajas talla 3 bebe seco con 372uds.', 372),
    ('Pack Dodot 3 cajas talla 3 bebe seco 558uds.', 558),
    ('Pack Dodot 4 cajas talla 3 bebe seco con 744uds.', 744),
    ('Paquete 62uds. Talla 3 Bebé-Seco Dodot (De 6 a 10Kg)', 62),
    ('Pañales Dodot Sensitive Talla 3  (6 a 10 kg.)- 56 uds', 56),
])
def test_inspected_standalone_title_grammars(title, units):
    # Titles recorded in the public probe report; no live availability/price claim.
    assert diaper_identity(title) == {'brand': 'Dodot', 'size': 3, 'units_per_pack': units}
    with pytest.raises(ValueError):
        diaper_identity(title + ' y champú')


@pytest.mark.parametrize('title', [
    'Pack Dodot talla 3 con 186uds y champú infantil',
    'Pañales talla 3 con 186uds bebé-seco ( 6 - 10 Kg ) Dodot con regalo sorpresa',
    'Lote higiene Dodot talla 3 186uds',
    'Pack Dodot 2 cajas talla 3 bebe seco con 372uds. y gel de baño',
])
def test_ambiguous_mixed_pack_rejected_from_product_fixture(title):
    async def check(page):
        node = page.locator('#product-details')
        data = json.loads(await node.get_attribute('data-product'))
        data['name'] = title  # Synthetic mutation; not a captured live mixed-pack title.
        await node.evaluate('(e,v)=>e.setAttribute("data-product",v)', json.dumps(data))
        with pytest.raises(ValueError, match='diaper'):
            await Nappy().extract(page, 'diapers', Nappy.product_urls[0])
    asyncio.run(with_page('nappy', check))


@pytest.mark.parametrize('field,value', [
    ('available_for_order', '0'), ('available_for_order', None),
    ('quantity', 0), ('quantity', -1), ('quantity', None), ('quantity', True),
])
def test_contradictory_or_missing_stock_evidence_is_not_available(field, value):
    async def check(page):
        node = page.locator('#product-details')
        data = json.loads(await node.get_attribute('data-product'))
        data[field] = value  # Synthetic mutations of real in-stock fixture.
        await node.evaluate('(e,v)=>e.setAttribute("data-product",v)', json.dumps(data))
        offer = await Nappy().extract(page, 'diapers', Nappy.product_urls[0])
        assert not offer.in_stock
    asyncio.run(with_page('nappy', check))
