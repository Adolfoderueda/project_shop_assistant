"""Explicit opt-in registrations. Bind managed contexts before calling adapters."""

from stores.amascotados import Amascotados
from stores.charro import Charro
from stores.mercadona import Mercadona
from stores.nappy import Nappy


def registrations():
    return [adapter().registration() for adapter in (Mercadona, Amascotados, Charro, Nappy)]
