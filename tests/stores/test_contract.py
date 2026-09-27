import pytest

from stores.base import StoreAdapter
from stores.registry import StoreRegistration, StoreRegistry


class Adapter:
    def capabilities(self): pass
    async def search(self, rule): pass
    async def quote(self, items, destination): pass
    async def prepare(self, quote): pass
    async def submit(self, cart, attempt_id): pass
    async def reconcile(self, attempt_id, cart): pass


def test_adapter_protocol_and_registry():
    adapter = Adapter()
    assert isinstance(adapter, StoreAdapter)
    entry = StoreRegistration("shop", adapter, frozenset({"shop.example"}),
                              frozenset({"cdn.example"}))
    registry = StoreRegistry([entry])
    assert registry.get("shop") == entry
    assert registry.adapters == {"shop": adapter}
    with pytest.raises(ValueError):
        StoreRegistry([entry, entry])
    with pytest.raises(KeyError):
        registry.get("unknown")


@pytest.mark.parametrize("store,host", [("../chrome", "shop.example"),
                                        ("shop", "*.example"), ("shop", "localhost"),
                                        ("shop", "127.0.0.1")])
def test_registration_rejects_unsafe_config(store, host):
    with pytest.raises(ValueError):
        StoreRegistration(store, Adapter(), frozenset({host}))
