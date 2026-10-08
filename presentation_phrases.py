"""Application-owned act variants, not arbitrary model prose or action authority."""

from presentation import PresentationPhrase, PresentationSnapshot

GREETINGS = ("¡Hola! ¿En qué te ayudo con tu lista?", "¡Hola! ¿Qué necesitas para tu lista?")
_CANCEL = "Cancelar: responde «cancelar»."


def presentation_variants(snapshot: PresentationSnapshot) -> tuple[PresentationPhrase, ...]:
    if snapshot.version == 1:
        return ()
    phrases = []
    for fact in snapshot.facts:
        token = "{{" + fact.key + "}}"
        variants = (token,)
        if snapshot.act in {"list", "select_entry"}:
            variants += ("• " + token,)
        elif snapshot.act == "greeting":
            variants += GREETINGS
        phrases.append(PresentationPhrase(key=fact.key, role="fact", variants=variants))
    if snapshot.question is not None:
        variants = ("{{q}}",)
        if any(option.text == _CANCEL for option in snapshot.options):
            variants += ("{{q}} Puedes cancelar.",)
        phrases.append(PresentationPhrase(key="q", role="question", variants=variants))
    for option in snapshot.options:
        token = "{{" + option.key + "}}"
        phrases.append(PresentationPhrase(key=option.key, role="option",
                                          variants=(token, "• " + token)))
    return tuple(phrases)


def phrase_compositions(
    snapshot: PresentationSnapshot,
) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], ...]:
    """Exact separate/grouped branches shared by schema and validator.

    Grouping only joins complete references with literal newlines. Bullet variants
    remain act-dependent; no punctuation, whitespace or connectors are inferred.
    """
    separate = tuple((p.role, p.variants) for p in snapshot.phrases)
    grouped = []
    for role in ("fact", "question", "option"):
        phrases = [p for p in snapshot.phrases if p.role == role]
        if not phrases:
            continue
        if len(phrases) == 1:
            grouped.append((role, phrases[0].variants))
        else:
            variants = ("\n".join(p.variants[0] for p in phrases),)
            if all("• {{" + p.key + "}}" in p.variants for p in phrases):
                variants += ("\n".join("• {{" + p.key + "}}" for p in phrases),)
            grouped.append((role, variants))
    result = tuple(grouped)
    return (separate,) if separate == result else (separate, result)
