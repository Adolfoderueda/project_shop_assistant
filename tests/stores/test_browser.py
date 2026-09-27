import asyncio
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

import pytest
from playwright.async_api import Error, Route

from stores.browser import BrowserManager, ProfileInUse, URLPolicy
from stores.registry import StoreRegistration, StoreRegistry


def registration():
    return StoreRegistration("shop", object(), frozenset({"shop.example"}),
                             frozenset({"cdn.example"}))


def policy(addresses=("93.184.216.34",)):
    return URLPolicy(registration(), resolver=AsyncMock(return_value=addresses))


@pytest.mark.parametrize("url", ["http://shop.example", "https://localhost",
    "https://127.0.0.1", "https://[::1]", "https://shop.example.evil.com",
    "https://evil.com", "https://u:p@shop.example", "https://shop.example:444",
    "https://shop.example\\@evil.com", "file:///secret"])
def test_unsafe_navigation_rejected(url):
    with pytest.raises(ValueError):
        asyncio.run(policy().validate(url))


def test_resource_policy_is_explicit_and_not_navigation_permission():
    asyncio.run(policy().validate("https://cdn.example/image", resource=True))
    with pytest.raises(ValueError):
        asyncio.run(policy().validate("https://cdn.example/checkout"))
    with pytest.raises(ValueError):
        asyncio.run(policy(("10.0.0.1",)).validate("https://shop.example"))


def test_redirect_is_checked_before_following():
    async def scenario():
        request = SimpleNamespace(url="https://shop.example/start",
                                  is_navigation_request=lambda: True)
        route = SimpleNamespace(request=request, abort=AsyncMock(), fulfill=AsyncMock(),
                                fetch=AsyncMock(return_value=SimpleNamespace(
                                    status=302, headers={"location": "https://127.0.0.1/"})))
        await policy().route(route)
        route.abort.assert_awaited_once()
        route.fulfill.assert_not_awaited()
        route.fetch.assert_awaited_once_with(max_redirects=0, max_retries=0)
    asyncio.run(scenario())


def test_profile_is_exclusive(tmp_path):
    async def scenario():
        registry = StoreRegistry([registration()])
        a, b = BrowserManager(tmp_path, registry), BrowserManager(tmp_path, registry)
        try:
            context = await a.open("shop")
            assert context.browser.browser_type.name == "chromium"
            with pytest.raises(ProfileInUse):
                await b.open("shop")
            with pytest.raises(ProfileInUse):
                await a.open("shop")
            child = await asyncio.to_thread(
                subprocess.run, [sys.executable, "-c", """
import asyncio, sys
from stores.browser import BrowserManager, ProfileInUse
from stores.registry import StoreRegistration, StoreRegistry
async def main():
    manager = BrowserManager(sys.argv[1], StoreRegistry([
        StoreRegistration('shop', object(), frozenset({'shop.example'}))]))
    try:
        await manager.open('shop')
    except ProfileInUse:
        print('exclusive')
    finally:
        await manager.close()
asyncio.run(main())
""", str(tmp_path)], capture_output=True, text=True, timeout=30)
            assert child.returncode == 0, child.stderr
            assert child.stdout.strip() == "exclusive"
        finally:
            await a.close()
            await b.close()
        try:
            await b.open("shop")
        finally:
            await b.close()
    asyncio.run(scenario())


def test_store_profiles_are_separate_and_external_navigation_blocked(tmp_path):
    async def scenario():
        second = StoreRegistration("other", object(), frozenset({"other.example"}))
        manager = BrowserManager(tmp_path, StoreRegistry([registration(), second]))
        try:
            first = await manager.open("shop")
            other = await manager.open("other")
            await first.add_cookies([{"name": "account", "value": "synthetic",
                                      "url": "https://shop.example"}])
            assert await other.cookies() == []
            page = await first.new_page()
            with pytest.raises(Error, match="ERR_BLOCKED_BY_CLIENT"):
                await page.goto("https://127.0.0.1/")
            assert (tmp_path / "shop").is_dir()
            assert (tmp_path / "other").is_dir()
        finally:
            await manager.close()
    asyncio.run(scenario())


def test_real_browser_redirect_chain_is_checked_each_hop(tmp_path, monkeypatch):
    # HTTP fixture is reached ONLY by this test's replacement fetch. Browser
    # URLs stay HTTPS, and the production policy still checks every redirect.
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "https://shop.example/mid" if self.path == "/start"
                             else "https://evil.example/stop")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    async def scenario():
        manager = BrowserManager(tmp_path, StoreRegistry([registration()]))
        seen = []
        try:
            context = await manager.open("shop")

            async def fixture_fetch(route, **kwargs):
                url = kwargs.pop("url", route.request.url)
                seen.append(url)
                path = urlsplit(url).path
                return await context.request.get(
                    f"http://127.0.0.1:{server.server_port}{path}", **kwargs)

            monkeypatch.setattr(Route, "fetch", fixture_fetch)
            await context.unroute("**/*")
            await context.route("**/*", policy().route)
            page = await context.new_page()
            with pytest.raises(Error):
                await page.goto("https://shop.example/start")
            assert seen == ["https://shop.example/start", "https://shop.example/mid"]
        finally:
            await manager.close()

    try:
        asyncio.run(scenario())
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_launch_failure_releases_profile(tmp_path, monkeypatch):
    async def scenario():
        from playwright.async_api import BrowserType

        manager = BrowserManager(tmp_path, StoreRegistry([registration()]))
        original = BrowserType.launch_persistent_context
        try:
            monkeypatch.setattr(BrowserType, "launch_persistent_context",
                                AsyncMock(side_effect=RuntimeError("launch failed")))
            with pytest.raises(RuntimeError, match="launch failed"):
                await manager.open("shop")
            monkeypatch.setattr(BrowserType, "launch_persistent_context", original)
            await manager.open("shop")
        finally:
            await manager.close()
    asyncio.run(scenario())
