"""Only confirmed restrictions; formula stays disabled pending reference check."""

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
