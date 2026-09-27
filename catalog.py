"""Only confirmed restrictions; formula stays disabled pending reference check."""

import re
import unicodedata

from domain import ProductRule

PRODUCT_RULES = (
    ProductRule(
        id="dog-food",
        brand="Alpha Spirit",
        variant="Wild Fish / Only Fish",
        grams=12000,
        gtin="8436586310295",
        verified=True,
    ),
    ProductRule(id="diapers", brand="Dodot", size=3, verified=True),
    ProductRule(id="formula", brand="Blemil", variant="Evolution", stage=1, verified=False),
)

DOG_URL = (
    "https://www.amascotados.com/alpha-spirit/"
    "2883-alpha-spirit-seco-only-fish-12-kg-8436586310295.html"
)


def resolve_product(description: str) -> str | None:
    """Household aliases identify restrictions, never invent offer metadata."""
    text = "".join(
        c for c in unicodedata.normalize("NFD", description.lower()) if not unicodedata.combining(c)
    ).strip()
    text = re.sub(r"^(?:paquetes?|botes?|sacos?|envases?|unidades?)\s+(?:de\s+)?", "", text)
    aliases = {
        "panales": "diapers",
        "dodot": "diapers",
        "dodot talla 3": "diapers",
        "panales dodot talla 3": "diapers",
        "pienso": "dog-food",
        "alpha spirit wild fish 12 kg": "dog-food",
        "alpha spirit only fish 12 kg": "dog-food",
        DOG_URL: "dog-food",
        "8436586310295": "dog-food",
        "formula": "formula",
        "leche": "formula",
        "blemil": "formula",
        "blemil tipo 1 evolution": "formula",
        "blemil 1 evolution": "formula",
    }
    return aliases.get(text)
