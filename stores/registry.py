"""Trusted local registry; websites cannot extend network permissions."""

import ipaddress
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from stores.base import StoreAdapter


def validate_host(host: str) -> None:
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host):
        raise ValueError("An exact lowercase DNS host is required")
    if "." not in host or any(not part or len(part) > 63 or
                              part.startswith("-") or part.endswith("-")
                              for part in host.split(".")):
        raise ValueError("Invalid DNS host")
    if host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Local hosts are forbidden")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return
    raise ValueError("IP literals are forbidden")


@dataclass(frozen=True)
class StoreRegistration:
    store_id: str
    adapter: StoreAdapter
    navigation_hosts: frozenset[str]
    resource_hosts: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", self.store_id):
            raise ValueError("Unsafe store ID")
        object.__setattr__(self, "navigation_hosts", frozenset(self.navigation_hosts))
        object.__setattr__(self, "resource_hosts", frozenset(self.resource_hosts))
        if not self.navigation_hosts:
            raise ValueError("Navigation policy cannot be empty")
        for host in self.navigation_hosts | self.resource_hosts:
            validate_host(host)


class StoreRegistry:
    def __init__(self, entries: Iterable[StoreRegistration] = ()):
        self._entries = {}
        for entry in entries:
            if entry.store_id in self._entries:
                raise ValueError("Duplicate store ID")
            self._entries[entry.store_id] = entry

    def get(self, store_id: str) -> StoreRegistration:
        return self._entries[store_id]

    @property
    def adapters(self) -> dict[str, StoreAdapter]:
        return {key: entry.adapter for key, entry in self._entries.items()}
