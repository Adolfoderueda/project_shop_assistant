from domain import Offer, ProductRule


def validate_product(rule: ProductRule, offer: Offer) -> list[str]:
    """Reject missing or different identity evidence, not merely similar titles."""
    reasons = []
    if not rule.verified:
        reasons.append("Referencia pendiente de cotejo")
    if not offer.in_stock:
        reasons.append("Sin existencias")
    for field in ("brand", "variant", "stage", "size", "grams", "gtin"):
        expected, actual = getattr(rule, field), getattr(offer, field)
        if expected is None:
            continue
        if field == "variant" and rule.id == "dog-food":
            matches = actual in ("Only Fish", "Wild Fish", "Wild Fish / Only Fish")
        else:
            matches = actual == expected
        if not matches:
            reasons.append(f"Identidad incompatible: {field}")
    return reasons
