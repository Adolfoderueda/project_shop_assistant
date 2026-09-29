"""Dated public product observations, separate from executable offers."""

import re
import sqlite3
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class ObservedProduct:
    id: str
    store_id: str
    product_id: str
    title: str
    url: str
    observed_on: str
    price_cents: int | None
    availability: bool | None
    format_note: str | None


def _tokens(text: str) -> set[str]:
    normalized = "".join(
        char for char in unicodedata.normalize("NFD", text.casefold())
        if not unicodedata.combining(char)
    )
    return set(re.findall(r"[a-z0-9]+", normalized))


def identifiable_product_name(name: str) -> bool:
    """A category/attribute alone is not a product to research."""
    generic = {
        "de", "del", "el", "la", "los", "las", "un", "una", "que",
        "producto", "productos", "articulo", "articulos", "cosa", "cosas",
        "ficha", "fichas", "precio", "precios", "stock", "disponibilidad",
    }
    return bool(_tokens(name) - generic)


def _record_missing_product(db: sqlite3.Connection, name: str) -> None:
    """Record only a minimal product name inside the caller's transaction."""
    normalized = " ".join(name.casefold().split())
    normalized = "".join(
        char for char in unicodedata.normalize("NFD", normalized)
        if not unicodedata.combining(char)
    )
    if not normalized:
        raise ValueError("Product name is required")
    db.execute("INSERT OR IGNORE INTO product_requests(name) VALUES (?)", (normalized,))


def matches_observation(query: str, product: ObservedProduct) -> bool:
    """Match whole product tokens and a closed set of category aliases only."""
    words = _tokens(query) - {"de", "del", "el", "la", "los", "las", "un", "una", "que", "precio"}
    if not words:
        return False
    aliases = {"panales": "dodot", "panal": "dodot", "formula": "blemil", "pienso": "alpha"}
    words = {aliases.get(word, word) for word in words}
    return words <= _tokens(product.title)
