"""Synthetic fixtures for pure agent tests; no persistence or model calls."""

from datetime import UTC, datetime

from domain import IncomingMessage, ListLine
from shopping_agent.contracts import AgentSnapshot

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)


def message(text="Necesito arroz y carne", update_id=10, **changes):
    return IncomingMessage(update_id=update_id, user_id=1, chat_id=2, text=text, **changes)


def line(id="a", description="arroz", quantity=1, revision=1):
    return ListLine(id=id, description=description, quantity=quantity, revision=revision)


def snapshot(proposal=None, lines=(), reservations=()):
    return AgentSnapshot(proposal=proposal, lines=lines, reservations=reservations,
                         user_id=1, chat_id=2, source_update_id=10,
                         original_text="Necesito arroz y carne")
