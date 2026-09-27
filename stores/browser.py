"""Visible dedicated Chromium profiles with fail-closed network routing.

    This is application policy, not an OS network sandbox. Registry entries and
    adapters are trusted local code, never generated from website instructions.
"""

import asyncio
import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from playwright.async_api import BrowserContext, Error, async_playwright

from stores.registry import StoreRegistration, StoreRegistry, validate_host


class ProfileInUse(RuntimeError):
    pass


async def _resolve(host: str) -> tuple[str, ...]:
    results = await asyncio.to_thread(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM)
    return tuple({item[4][0] for item in results})


class URLPolicy:
    def __init__(self, registration: StoreRegistration, *, resolver=_resolve):
        self.registration, self.resolver = registration, resolver

    async def validate(self, url: str, *, resource: bool = False) -> None:
        if any(ord(c) <= 32 for c in url) or "\\" in url:
            raise ValueError("Unsafe URL")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.port not in (None, 443)):
            raise ValueError("Only public HTTPS URLs without credentials are allowed")
        host = parsed.hostname
        validate_host(host)
        hosts = self.registration.navigation_hosts
        if resource:
            hosts = hosts | self.registration.resource_hosts
        if host not in hosts:
            raise ValueError("Host is not explicitly allowed")
        addresses = await self.resolver(host)
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise ValueError("Host must resolve only to public addresses")

    async def route(self, route) -> None:
        request = route.request
        resource = not request.is_navigation_request()
        try:
            await self.validate(request.url, resource=resource)
            # Browser redirects bypass Playwright routing, even after fulfill.
            # Fetch hops ourselves; NEVER fulfill a redirect into the browser.
            # Only read-only same-host GET/HEAD redirects are followed. Other
            # redirects require intervention; never replay a checkout POST.
            response = await route.fetch(max_redirects=0, max_retries=0)
            current = request.url
            hops = 0
            while 300 <= response.status < 400 and "location" in response.headers:
                target = urljoin(current, response.headers["location"])
                await self.validate(target, resource=resource)
                if (request.method not in ("GET", "HEAD") or hops >= 10
                        or urlsplit(target).hostname != urlsplit(current).hostname):
                    raise ValueError("Redirect requires intervention")
                response = await route.fetch(url=target, max_redirects=0, max_retries=0)
                current = target
                hops += 1
            # Manual fetch retains the original browser URL/base URI. Adapters
            # must navigate canonical URLs; redirect-heavy sites need inspection.
            await route.fulfill(response=response)
        except (ValueError, OSError, Error):
            await route.abort("blockedbyclient")


class BrowserManager:
    def __init__(self, profiles_dir: str | Path, registry: StoreRegistry):
        self.profiles_dir = Path(profiles_dir).resolve()
        self.registry = registry
        self._contexts = {}
        self._locks = {}
        self._playwright = None
        self._guard = asyncio.Lock()

    async def open(self, store_id: str) -> BrowserContext:
        async with self._guard:
            registration = self.registry.get(store_id)
            profile = self.profiles_dir / store_id
            profile.mkdir(parents=True, exist_ok=True)
            # OS lock, not just an in-process mutex; release automatically on crash.
            lock = (profile / ".assistant.lock").open("a+b")
            try:
                if os.name == "nt":
                    import msvcrt
                    lock.seek(0)
                    if not lock.read(1):
                        lock.write(b"0")
                        lock.flush()
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                lock.close()
                raise ProfileInUse("Store profile is already in use") from None
            context = None
            try:
                if self._playwright is None:
                    self._playwright = await async_playwright().start()
                context = await self._playwright.chromium.launch_persistent_context(
                    str(profile), headless=False, service_workers="block",
                    accept_downloads=False,
                )
                policy = URLPolicy(registration)
                await context.route("**/*", policy.route)
                # WebSockets have separate routing and no inspected use yet.
                await context.route_web_socket("**/*", lambda ws: ws.close())
                self._contexts[store_id] = context
                self._locks[store_id] = lock
                return context
            except BaseException:
                if context is not None:
                    await context.close()
                lock.close()
                raise

    async def close(self) -> None:
        async with self._guard:
            try:
                for context in self._contexts.values():
                    await context.close()
            finally:
                if self._playwright is not None:
                    await self._playwright.stop()
                    self._playwright = None
                self._contexts.clear()
                for lock in self._locks.values():
                    lock.close()
                self._locks.clear()
