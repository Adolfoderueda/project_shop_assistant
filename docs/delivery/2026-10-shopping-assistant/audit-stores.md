# Store adapter and price-evidence audit (TAK-10 / GitHub #14)

Observed 2026-10-12 by Store Integration Engineer. Independent reviewer: QA Release Engineer (TAK-11 / #15). Approved product baseline: `b9a29049160cc53737d1cb64a8138385aa2fedd2`. PR #11 head at branch creation: `27536aea3047da546ad1242c7dfef207f9011476`. PR #11 changes no owned store, product-memory, catalog, offer, or store-test paths; this source review and the focused offline runs used the identical owned baseline. This report and its repair are on the TAK-10 branch based on that PR head. Neither PR approval nor release acceptance is asserted.

## Source coverage

Every path in the assigned owned set was read in full. This is manual source review, separate from test execution. No repository `AGENTS.md` was present at the reviewed baseline.

| Area | Paths read in full | Observation |
| --- | --- | --- |
| Store contracts and browser policy | `stores/__init__.py`, `stores/base.py`, `stores/browser.py`, `stores/connections.py`, `stores/registry.py` | Four explicit registrations; read-only public capabilities; exact host and public-address routing; disabled purchase path. Browser routing is application policy, not an OS sandbox. |
| Store parsing | `stores/public.py`, `stores/mercadona.py`, `stores/amascotados.py`, `stores/charro.py`, `stores/nappy.py` | Mercadona checks CP 28023. Product parsers use bounded formats. Quotes omit shipping and total. Findings below. |
| Product and comparison | `catalog.py`, `offers.py`, `product_memory.py` | Verified rules filter candidate identity; historical observations are separate from offers. Complete-basket ranking requires known shipping/total. |
| Store tests | `tests/stores/test_amascotados.py`, `tests/stores/test_browser.py`, `tests/stores/test_charro.py`, `tests/stores/test_contract.py`, `tests/stores/test_mercadona.py`, `tests/stores/test_nappy.py`, `tests/stores/test_public_adapters.py` | Synthetic offline tests cover host policy, public extraction, stock and disabled purchase methods. |
| Store fixtures | `tests/fixtures/stores/amascotados.html`, `tests/fixtures/stores/charro.html`, `tests/fixtures/stores/mercadona-search.html`, `tests/fixtures/stores/mercadona.html`, `tests/fixtures/stores/nappy-out.html`, `tests/fixtures/stores/nappy.html` | Sanitized September public captures. Fixture prices are historical, never a current check. |
| Product tests and evidence document | `tests/test_offers.py`, `tests/test_product_memory.py`, `tests/test_product_queries.py`, `docs/store-capabilities.md` | Tests distinguish stored historical observations and unknown delivery cost; the document dates site inspection 2026-09-27/28. Its earlier DONE_WITH_CONCERNS and test counts are historical, not a 2026-10-12 live result. |

## Findings and disposition

| Severity | Finding, reproduction, and disposition |
| --- | --- |
| High, repaired in this PR | `PublicStore.quote` reloaded price from the same URL but accepted a changed pack/variant. The same line and pack count could therefore silently represent fewer pieces. The new synthetic `test_quote_rejects_changed_pack_on_same_product_url` changes a Nappy 186-unit fixture to a valid 56-unit title on the same URL; baseline failed with `DID NOT RAISE ValueError` (exit 1). The repair compares stable identity fields before returning the refreshed offer. Price, stock and observation time may still change and remain visible. |
| Medium, P3 handoff | `PublicStore.search` catches `ValueError` for discovered listing links and drops them. That includes both intended unsupported mixed bundles and changed/invalid public pages, so search cannot prove complete coverage. P3 must distinguish an incompatible product from a failed observation and expose partial coverage to the read-only price tool. Current code must not claim market-wide cheapest. Owner: Store Integration Engineer on P3, after P0 and interface review. |
| Medium, P3 handoff | `Mercadona.discover` waits for a first search result; an empty result or changed selector can time out instead of yielding an explicit empty/unknown result. The current timeout remains a failed check, not out-of-stock evidence. P3 should add a bounded empty-result fixture and typed status before live refresh. Owner: Store Integration Engineer on P3. |
| Medium, shared boundary | The native agent's `consultar_ficha` in `shopping_agent/tools.py` is historical-only and returns `historical_only=True`; it is not a fresh price tool. P3 needs an independently reviewed read-only interface and any storage/schema change coordinated with Python Agent Engineer. No such interface or migration is implemented here. Owner: Mushu routes interface review with Python Agent Engineer before P3 implementation. |

The existing `select_assignments` rejects a quote whose refreshed offer differs from the supplied candidate, including a changed price. That is conservative for ranking: it returns incomplete coverage instead of using stale totals. The future price tool must render the newly observed value separately from ranking, with its own time and source; a failed refresh must retain the cached label.

## Evidence and limits

- Current authorized site observations in this audit: **none**. No public site was contacted. Mercadona 28023 56-unit Dodot Sensitive at 16.95 EUR is a **2026-09-28 historical observation** in `docs/store-capabilities.md` and the fixture, not a 2026-10-12 price. Nappy and the other stored prices are likewise historical.
- The `Offer.observed_at` timestamp is set during extraction. A source URL and exact pack fields accompany the offer. A cached `ObservedProduct.observed_on` date never proves today's price or stock. Page text is untrusted data; it cannot change product rules, host policy, model authority or purchase capabilities.
- In the four public adapters, `prepare=False`, `submit=False`, `reconcile=False`, `live_verified=False`. `prepare` refuses, `submit` reports intervention without action and `reconcile` remains unknown. No order or non-submission proof is inferred.
- `PublicStore.quote` leaves shipping, total and delivery as `None`. `rank_quotes` accepts only complete totals. Unknown shipping stays unknown; no delivered-basket cheapest claim is supported by these adapters.
- Existing synthetic coverage includes wrong region, wrong packs/mixed bundles, Nappy unavailable capture, changed price input, unknown stock, and blocked purchase calls. A real site timeout, changed price, and availability for October 12 were **not** observed. A timeout is a failed observation, never a zero price or unavailable-product claim.

## Executed commands and results

Executed in an isolated scratch worktree of `b9a29049160cc53737d1cb64a8138385aa2fedd2` with the existing project Python environment and synthetic fixtures. PR #11 did not modify the owned source paths. No private data, live Telegram/model probe, bot restart, site browsing or purchase was used.

| Command | Result |
| --- | --- |
| `python -m pytest -q tests/stores tests/test_offers.py tests/test_product_memory.py tests/test_product_queries.py` on untouched baseline | Exit 0, 136 passed in 35.78 s. This is a focused offline run, not a whole-suite pass. |
| `python -m pytest -q tests/stores/test_public_adapters.py::test_quote_rejects_changed_pack_on_same_product_url` before repair | Exit 1, one failure: expected `ValueError` but quote returned changed pack. This is the RED reproduction. |
| `python -m pytest -q tests/stores tests/test_offers.py tests/test_product_memory.py tests/test_product_queries.py` after repair | Exit 0, 137 passed in 23.17 s. |
| `python -m ruff check stores/public.py tests/stores/test_public_adapters.py` after repair | Exit 0, all checks passed. |
| `git diff --check` after repair | Exit 0. |

An additional synthetic boundary check ran with the existing project Python as `python -` (PowerShell here-string on stdin), exit 0. It changed a Nappy offer from 4687 to 4999 cents and to unavailable, asserted the quote carried the new values with `shipping_cents` and `total_cents` still `None`, then made `read_product` raise `TimeoutError` and asserted that no cached quote was returned. The executable body was:

```python
import asyncio
from datetime import UTC, datetime
from domain import Destination, Offer, QuotedLine
from stores.nappy import Nappy
offer = Offer(store_id='nappy', product_id='diapers', url=Nappy.product_urls[0],
              title='Pañales talla 3 con 186uds bebé-seco ( 6 - 10 Kg ) Dodot',
              brand='Dodot', size=3, units_per_pack=186, price_cents=4687,
              in_stock=True, conditions=[], observed_at=datetime.now(UTC))
line = QuotedLine(line_id='synthetic', offer=offer, packs=1)
destination = Destination(postcode='28023', address='Synthetic only')
async def run():
    store = Nappy()
    async def changed(url, product_id):
        return offer.model_copy(update={'price_cents': 4999, 'in_stock': False,
                                         'observed_at': datetime.now(UTC)})
    store.read_product = changed
    quote = await store.quote([line], destination)
    assert quote.items[0].offer.price_cents == 4999
    assert quote.items[0].offer.in_stock is False
    assert quote.shipping_cents is None and quote.total_cents is None
    async def timeout(url, product_id):
        raise TimeoutError('synthetic timeout')
    store.read_product = timeout
    try:
        await store.quote([line], destination)
    except TimeoutError:
        pass
    else:
        raise AssertionError('timeout was swallowed')
asyncio.run(run())
```

Full offline suite and PR CI remain parent/integration gates. Current public-site smoke check is pending specific P3 authorization. QA should review the TAK-10 PR diff and focused evidence at its exact SHA; Mushu should route the P3 interface and shared ownership findings. Takeshi retains final acceptance and merge.

